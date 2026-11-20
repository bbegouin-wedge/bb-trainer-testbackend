"""Le harnais commun : une doublure en mémoire, son horloge, ses coachs.

La doublure est montée dans une seule application (canaux et console), servie
par le client de test de Starlette : tout tourne dans la même boucle, sans
réseau. L'horloge est fausse : elle n'avance que si le test le demande.
"""

import json
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from testbackend.app import create_app
from testbackend.backend import Backend
from testbackend.scenario.runner import Runner

HOME = "01JCQ4K2H8P5S7D3F9A1E6C0QM"
VISITOR = "01JCQ4K9R3T6W8Y2B5N1M4V7XZ"
GAME = "01JCQ4M8Z7T2V9K3X5R1N6B0WD"
STRANGER = "01JCQ4KZZZZZZZZZZZZZZZZZZZ"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class CoachSocket:
    """La socket d'un coach de test : ce qu'il lit, ce qu'il envoie."""

    ws: WebSocketTestSession

    def next(self) -> dict[str, Any]:
        frame: dict[str, Any] = self.ws.receive_json()
        return frame

    def next_text(self) -> str:
        return self.ws.receive_text()

    def frames(self, count: int) -> list[dict[str, Any]]:
        return [self.next() for _ in range(count)]

    def command(self, command: dict[str, Any], **extra: Any) -> None:
        self.ws.send_text(json.dumps({"command": command, **extra}))

    def raw(self, text: str) -> None:
        self.ws.send_text(text)

    def closed_with(self) -> int:
        """Le code de fermeture, une fois la socket fermée par le serveur."""
        try:
            self.ws.receive_text()
        except WebSocketDisconnect as disconnect:
            return disconnect.code
        raise AssertionError("la socket est restée ouverte")


@dataclass
class Harness:
    client: TestClient
    backend: Backend
    clock: FakeClock
    runner: Runner
    stack: ExitStack = field(default_factory=ExitStack)

    def create_game(self, **ids: str) -> dict[str, Any]:
        body = {
            "game_id": GAME,
            "home_coach": HOME,
            "visitor_coach": VISITOR,
            **ids,
        }
        response = self.client.post("/pilot/games", json=body)
        assert response.status_code == 201, response.text
        created: dict[str, Any] = response.json()
        return created

    def connect(self, coach_id: str = HOME, game_id: str = GAME) -> CoachSocket:
        url = f"/games/{game_id}/coaches/{coach_id}/ws"
        return CoachSocket(self.stack.enter_context(self.client.websocket_connect(url)))

    def join(self, coach_id: str = HOME) -> CoachSocket:
        """Se connecte et lit l'accusé de la jonction."""
        coach = self.connect(coach_id)
        assert coach.next()["type"] == "accepted"
        return coach

    def act(self, action: dict[str, Any], game_id: str = GAME) -> Response:
        response: Response = self.client.post(
            f"/pilot/games/{game_id}/actions", json=action
        )
        return response

    def do(self, action: dict[str, Any], game_id: str = GAME) -> None:
        response = self.act(action, game_id)
        assert response.status_code == 204, response.text

    def settings(self, **changes: Any) -> None:
        response = self.client.patch("/pilot/settings", json=changes)
        assert response.status_code == 200, response.text

    def journal(self, game_id: str = GAME) -> dict[str, Any]:
        response = self.client.get(f"/games/{game_id}/journal")
        assert response.status_code == 200, response.text
        snapshot: dict[str, Any] = response.json()
        return snapshot

    def wire(self, side: str | None = None) -> list[str]:
        """Les libellés du fil, d'un coach ou de tous."""
        return [
            e["kind"]
            for e in self.journal()["wire"]
            if side is None or e["side"] == side
        ]

    def judge(self, number: int, **verdict: Any) -> Response:
        response: Response = self.client.post(
            f"/pilot/games/{GAME}/pending/{number}/verdict", json=verdict
        )
        return response

    def pending(self) -> list[dict[str, Any]]:
        pending: list[dict[str, Any]] = self.journal()["pending"]
        return pending

    def wait_pending(self, count: int = 1) -> list[dict[str, Any]]:
        """Attend que `count` commandes lues attendent leur jugement."""
        for _ in range(200):
            if len(pending := self.pending()) >= count:
                return pending
        raise AssertionError(
            f"{count} commande(s) à juger attendue(s) : {self.pending()}"
        )


def build_harness(scenarios: Path | None = None) -> tuple[Harness, ExitStack]:
    clock = FakeClock()
    backend = Backend(clock=clock)
    runner = Runner(backend, scenarios or Path("/nonexistent"))
    stack = ExitStack()
    client = stack.enter_context(TestClient(create_app(backend, runner)))
    harness = Harness(client, backend, clock, runner)
    return harness, stack


def request_to(to: str, key: str = "kick_off_choice", **extra: Any) -> dict[str, Any]:
    """L'action qui ouvre une demande du catalogue."""
    return {
        "do": "request",
        "to": to,
        "key": key,
        "options": {"accepts": ["choose_kick_off"], "choices": ["kick", "receive"]},
        **extra,
    }


KICK = {"type": "choose_kick_off", "choice": "kick"}
