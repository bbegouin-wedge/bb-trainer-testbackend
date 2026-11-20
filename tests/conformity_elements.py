from typing import Any

from tests.harness import Harness


def then_the_rules_read(harness: Harness, **expected: str) -> None:
    statuses = {r["rule"]: r["status"] for r in harness.journal()["conformity"]}
    for rule, status in expected.items():
        assert statuses[rule.replace("R422", "422")] == status, (rule, statuses)


def then_the_deviation_reads(
    harness: Harness, rule: str, side: str, detail: str
) -> None:
    report: dict[str, Any] = next(
        r for r in harness.journal()["conformity"] if r["rule"] == rule
    )
    assert {"side": side, "detail": detail} in report["deviations"], report
