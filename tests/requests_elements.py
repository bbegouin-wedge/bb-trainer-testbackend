from typing import Any

from tests.harness import GAME, HOME, KICK, VISITOR, CoachSocket, Harness, request_to


def given_two_joined_coaches(harness: Harness) -> tuple[CoachSocket, CoachSocket]:
    harness.create_game()
    return harness.join(HOME), harness.join(VISITOR)


def given_a_kick_off_request(
    harness: Harness, home: CoachSocket, **extra: Any
) -> dict[str, Any]:
    harness.do(request_to("home", **extra))
    return home.next()


def when_the_operator_opens(harness: Harness, action: dict[str, Any]) -> None:
    harness.do(action)


def when_the_coach_sends(
    coach: CoachSocket, command: dict[str, Any] = KICK, **extra: Any
) -> None:
    coach.command(command, **extra)


def then_it_receives_the_request(
    coach: CoachSocket,
    key: str,
    request_id: int,
    coach_id: str | None = HOME,
    **options: Any,
) -> None:
    frame = coach.next()
    expected_options = {"to": "coach", "coach_id": coach_id} if coach_id else {}
    expected_options |= options or {
        "accepts": ["choose_kick_off"],
        "choices": ["kick", "receive"],
    }
    assert frame == {
        "type": "request",
        "key": key,
        "request_id": request_id,
        "options": expected_options,
    }


def then_it_receives(coach: CoachSocket, **expected: Any) -> dict[str, Any]:
    frame = coach.next()
    for key, value in expected.items():
        assert frame[key] == value, frame
    return frame


def then_it_is_accepted(coach: CoachSocket, command: dict[str, Any] = KICK) -> None:
    frame = coach.next()
    assert frame == {"type": "accepted", "command": command}, frame


def then_it_is_refused(coach: CoachSocket, status: int, detail: str) -> None:
    frame = coach.next()
    assert frame["type"] == "refused" and frame["status"] == status, frame
    assert detail in frame["detail"], frame


def then_the_open_requests_are(harness: Harness, *refs: tuple[str, int]) -> None:
    assert [(r["key"], r["request_id"]) for r in harness.journal()["requests"]] == list(
        refs
    )


def then_the_action_is_refused(
    harness: Harness, action: dict[str, Any], status: int, detail: str
) -> None:
    response = harness.act(action)
    assert response.status_code == status, response.text
    assert detail in response.text


def then_the_frame_was_lost(harness: Harness, side: str, label: str) -> None:
    entry = [
        e for e in harness.journal()["wire"] if e["kind"] == label and e["side"] == side
    ][-1]
    assert entry["note"] == "perdue : coach absent"


def then_the_wire_warns(harness: Harness, label: str) -> None:
    assert any(
        e["kind"] == label and e["level"] == "warn" for e in harness.journal()["wire"]
    )


def not_waiting() -> str:
    return f"le dossier {GAME} n'attend aucune entrée"


def ambiguous() -> str:
    return f"la partie {GAME} attend plusieurs réponses de {HOME}"
