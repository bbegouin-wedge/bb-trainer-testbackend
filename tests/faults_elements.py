from typing import Any

from tests.harness import CoachSocket, Harness


def when_the_operator_arms(harness: Harness, **action: Any) -> None:
    harness.do(action)


def then_the_socket_closes_with(coach: CoachSocket, code: int) -> None:
    assert coach.closed_with() == code


def then_it_reads_text(coach: CoachSocket, text: str) -> None:
    assert coach.next_text() == text


def then_the_wire_notes(harness: Harness, side: str, label: str, note: str) -> None:
    entries = [
        e for e in harness.journal()["wire"] if e["side"] == side and e["kind"] == label
    ]
    assert entries and entries[-1]["note"] == note, entries
