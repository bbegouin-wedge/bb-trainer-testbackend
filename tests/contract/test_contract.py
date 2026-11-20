"""La comparaison avec automaton : une même suite d'échanges, jouée contre la
doublure (à chaque `make test`) et contre le vrai serveur (`make
check-automaton`, qui demande AUTOMATON_DIR).

Les identifiants diffèrent forcément ; on compare les types de messages, les
codes, l'ordre, et le texte des refus que la doublure imite.
"""

import json
import os
from collections.abc import Iterator
from typing import Any

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from testbackend.ids import new_id
from tests.contract.targets import Target, automaton, doublure

KICK = {"type": "choose_kick_off", "choice": "kick"}


@pytest.fixture(
    params=["doublure", pytest.param("automaton", marks=pytest.mark.contract)]
)
def target(request: pytest.FixtureRequest) -> Iterator[Target]:
    if request.param == "automaton" and "AUTOMATON_DIR" not in os.environ:
        pytest.skip("AUTOMATON_DIR non renseigné")
    with doublure() if request.param == "doublure" else automaton() as t:
        yield t


class Coach:
    def __init__(self, target: Target, game_id: str, coach_id: str) -> None:
        self.coach_id = coach_id
        self.ws: ClientConnection = connect(
            f"{target.ws}/games/{game_id}/coaches/{coach_id}/ws"
        ).__enter__()
        self.backlog: list[dict[str, Any]] = []

    def next(self, timeout: float = 5) -> dict[str, Any]:
        if self.backlog:
            return self.backlog.pop(0)
        frame: dict[str, Any] = json.loads(self.ws.recv(timeout=timeout))
        return frame

    def until(self, type_: str) -> list[dict[str, Any]]:
        """Les trames jusqu'à la première de ce type, comprise."""
        frames = [self.next()]
        while frames[-1]["type"] != type_:
            frames.append(self.next())
        return frames

    def send(self, command: Any) -> None:
        self.ws.send(
            command if isinstance(command, str) else json.dumps({"command": command})
        )

    def close_code(self) -> int | None:
        try:
            self.ws.recv(timeout=5)
        except ConnectionClosed as closed:
            return closed.rcvd.code if closed.rcvd else None
        return None


def test_the_doublure_answers_like_automaton(target: Target) -> None:
    home_id, visitor_id, stranger = new_id(), new_id(), new_id()
    game_id = target.create_game(
        {
            "home_coach": home_id,
            "home_team": new_id(),
            "visitor_coach": visitor_id,
            "visitor_team": new_id(),
        }
    )

    unknown = new_id()
    lost = Coach(target, unknown, home_id)
    assert lost.next() == {
        "type": "refused",
        "status": 404,
        "detail": f"le dossier {unknown} n'existe pas",
    }
    assert lost.close_code() == 4404

    intruder = Coach(target, game_id, stranger)
    assert intruder.next() == {
        "type": "refused",
        "status": 403,
        "detail": f"{stranger} ne joue pas le match {game_id}",
    }
    assert intruder.close_code() == 4403

    home = Coach(target, game_id, home_id)
    assert home.next() == {
        "type": "accepted",
        "command": {"type": "join_game", "coach_id": home_id},
    }
    home.send(KICK)
    assert home.next() == {
        "type": "refused",
        "status": 409,
        "detail": f"le dossier {game_id} n'attend aucune entrée",
    }
    home.send("{")
    unreadable = home.next()
    assert unreadable["status"] == 422 and unreadable["detail"].startswith(
        "message illisible"
    )

    visitor = Coach(target, game_id, visitor_id)
    joined = visitor.until("accepted")
    assert joined[-1] == {
        "type": "accepted",
        "command": {"type": "join_game", "coach_id": visitor_id},
    }
    visitor.backlog = joined[:-1]

    target.offer_kick_off(game_id, "home")
    chooser, other = _the_chooser(home, visitor)
    request = chooser.next()
    assert request["type"] == "request" and request["key"] == "kick_off_choice"
    assert request["options"] == {
        "to": "coach",
        "coach_id": chooser.coach_id,
        "accepts": ["choose_kick_off"],
        "choices": ["kick", "receive"],
    }

    other.send(KICK)
    assert other.next()["status"] == 409

    chooser.ws.close()
    chooser = Coach(target, game_id, chooser.coach_id)
    assert (
        chooser.next() == request
    )  # rattrapage : la même demande, sans second accepted

    chooser.send({"type": "choose_kick_off", "choice": "recieve"})
    assert chooser.next()["status"] == 422
    chooser.send(KICK)
    assert chooser.until("accepted")[-1] == {"type": "accepted", "command": KICK}


def _the_chooser(home: Coach, visitor: Coach) -> tuple[Coach, Coach]:
    """Le coach à qui kick_off_choice est adressée (le tir au dé d'automaton)."""
    if any(f.get("key") == "kick_off_choice" for f in visitor.backlog):
        return visitor, home
    try:
        frame = home.next(timeout=3)
    except TimeoutError:
        return visitor, home
    home.backlog.insert(0, frame)
    return home, visitor
