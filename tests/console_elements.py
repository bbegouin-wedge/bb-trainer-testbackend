from typing import Any

from httpx import Response
from starlette.testclient import WebSocketTestSession

from tests.harness import GAME, HOME, KICK, CoachSocket, Harness, request_to


def given_a_manual_judge(harness: Harness) -> tuple[CoachSocket, CoachSocket]:
    harness.create_game()
    home, visitor = harness.join(HOME), harness.join("01JCQ4K9R3T6W8Y2B5N1M4V7XZ")
    harness.settings(judge="manual")
    harness.do(request_to("home"))
    assert home.next()["type"] == "request"
    return home, visitor


def given_a_command_to_judge(
    harness: Harness, home: CoachSocket, command: dict[str, Any] = KICK
) -> int:
    home.command(command)
    number: int = harness.wait_pending()[0]["number"]
    return number


def when_the_page_is_read(harness: Harness, path: str) -> Response:
    response: Response = harness.client.get(path, follow_redirects=False)
    return response


def when_the_operator_watches(harness: Harness) -> WebSocketTestSession:
    return harness.stack.enter_context(
        harness.client.websocket_connect(f"/ui/games/{GAME}/ws")
    )


def when_the_operator_judges(harness: Harness, number: int, **verdict: Any) -> Response:
    return harness.judge(number, **verdict)


def when_the_operator_stages(
    harness: Harness, number: int, action: dict[str, Any]
) -> Response:
    response: Response = harness.client.post(
        f"/pilot/games/{GAME}/pending/{number}/stage", json=action
    )
    return response


def then_it_shows(response: Response, *texts: str) -> None:
    assert response.status_code == 200, response.text
    for text in texts:
        assert text in response.text, text


def then_it_redirects_to(response: Response, location: str) -> None:
    assert response.status_code == 307
    assert response.headers["location"] == location


def then_a_push_shows(watcher: WebSocketTestSession, *texts: str) -> None:
    html = watcher.receive_text()
    for text in texts:
        assert text in html, text


def then_the_status_is(response: Response, status: int, detail: str = "") -> None:
    assert response.status_code == status, response.text
    assert detail in response.text


def then_nothing_waits(harness: Harness) -> None:
    assert harness.pending() == []
