"""Briques communes des tests given / when / then.

Un `when_…` dont l'action peut échouer rend une Attempt : le test vérifie
ensuite l'erreur avec then_it_fails_with, sans pytest.raises dans son corps.
"""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Attempt[T]:
    """Le résultat d'une action, ou l'erreur qu'elle a levée."""

    result: T | None
    error: Exception | None


def attempt[T](action: Callable[[], T]) -> Attempt[T]:
    try:
        return Attempt(result=action(), error=None)
    except Exception as err:
        return Attempt(result=None, error=err)


def then_it_fails_with(
    outcome: Attempt[object], error: type[Exception], message: str = ""
) -> None:
    assert isinstance(outcome.error, error), outcome.error
    assert message in str(outcome.error)
