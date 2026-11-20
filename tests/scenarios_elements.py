import json
import time
from pathlib import Path
from typing import Any

from httpx import Response

from tests.harness import GAME, HOME, VISITOR, Harness

IDS = {"game_id": GAME, "home_coach": HOME, "visitor_coach": VISITOR}


def given_a_scenario(
    directory: Path, steps: list[dict[str, Any]], name: str = "s.json", **extra: Any
) -> str:
    body = {"name": name, "game": IDS, "steps": steps, **extra}
    (directory / name).write_text(json.dumps(body), encoding="utf-8")
    return name


def when_it_runs(harness: Harness, file: str, **extra: Any) -> Response:
    response: Response = harness.client.post(
        "/pilot/scenarios/run", json={"file": file, **extra}
    )
    return response


def when_it_is_controlled(harness: Harness, command: str) -> Response:
    response: Response = harness.client.post(f"/pilot/scenarios/{command}")
    return response


def then_the_state_becomes(
    harness: Harness, status: str, timeout: float = 5
) -> dict[str, Any]:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        state: dict[str, Any] = harness.client.get("/pilot/scenarios/state").json()
        if state["status"] == status:
            return state
        time.sleep(0.01)
    raise AssertionError(
        f"état {status} attendu : {harness.client.get('/pilot/scenarios/state').json()}"
    )


def then_it_failed_with(harness: Harness, error: str) -> None:
    state = then_the_state_becomes(harness, "failed")
    assert error in state["error"], state["error"]
