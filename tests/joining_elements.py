from typing import Any

from httpx import Response

from tests.harness import GAME, HOME, VISITOR, CoachSocket, Harness


def given_a_game(harness: Harness) -> None:
    harness.create_game()


def when_a_game_is_created(harness: Harness, route: str, **body: Any) -> Response:
    response: Response = harness.client.post(route, json=body)
    return response


def when_the_coach_connects(
    harness: Harness, coach_id: str = HOME, game_id: str = GAME
) -> CoachSocket:
    return harness.connect(coach_id, game_id)


def then_it_is_created(response: Response, **expected: str) -> None:
    assert response.status_code == 201, response.text
    for key, value in expected.items():
        assert response.json()[key] == value


def then_only_the_game_id_is_returned(response: Response) -> None:
    assert response.status_code == 201
    assert list(response.json()) == ["game_id"]


def then_it_is_refused(response: Response, status: int, detail: str) -> None:
    assert response.status_code == status, response.text
    assert detail in response.text


def then_the_ids_are_drawn(response: Response) -> None:
    created = response.json()
    assert len({created[k] for k in created}) == 5


def then_the_channel_is_refused(
    coach: CoachSocket, status: int, close_code: int, detail: str
) -> None:
    frame = coach.next()
    assert frame["type"] == "refused"
    assert frame["status"] == status
    assert detail in frame["detail"]
    assert coach.closed_with() == close_code


def then_the_join_is_accepted(coach: CoachSocket, coach_id: str = HOME) -> None:
    assert coach.next() == {
        "type": "accepted",
        "command": {"type": "join_game", "coach_id": coach_id},
    }


def when_the_coach_reconnects(
    harness: Harness, first: CoachSocket, coach_id: str = HOME
) -> CoachSocket:
    first.ws.close()
    return harness.connect(coach_id)


def then_the_wire_reads(harness: Harness, side: str | None, *labels: str) -> None:
    assert harness.wire(side) == list(labels)


def then_the_coaches_have_joined(harness: Harness) -> None:
    coaches = harness.journal()["coaches"]
    assert coaches["home"]["joined"] and coaches["visitor"]["joined"]
    assert coaches["home"]["coach_id"] == HOME
    assert coaches["visitor"]["coach_id"] == VISITOR


def when_the_journal_is_read(harness: Harness, game_id: str) -> Response:
    response: Response = harness.client.get(f"/games/{game_id}/journal")
    return response
