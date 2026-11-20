from typing import Any

from tests.harness import CoachSocket, Harness

ROLL_OFF = {"type": "roll_off_won", "side": "home"}
KICKING = {"type": "kicking_team_chosen", "side": "visitor"}


def when_a_fact_is_emitted(
    harness: Harness, fact: dict[str, Any] = ROLL_OFF, **extra: Any
) -> None:
    harness.do({"do": "fact", "fact": fact, **extra})


def then_it_receives_the_fact(
    coach: CoachSocket, seq: int, fact: dict[str, Any] = ROLL_OFF
) -> None:
    assert coach.next() == {"type": "fact", "seq": seq, "fact": fact}


def then_the_facts_are(harness: Harness, *expected: tuple[int, str]) -> None:
    assert [(f["seq"], f["fact"]["type"]) for f in harness.journal()["facts"]] == list(
        expected
    )
