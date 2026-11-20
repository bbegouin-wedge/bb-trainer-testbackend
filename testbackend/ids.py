"""Les identifiants : des ULID, écrits en chaîne comme sur le fil."""

from typing import Any, Literal

from ulid import ULID

from testbackend.errors import InvalidInput

type Side = Literal["home", "visitor"]
SIDES: tuple[Side, Side] = ("home", "visitor")
SIDE_LABEL: dict[Side, str] = {"home": "domicile", "visitor": "visiteur"}


def new_id() -> str:
    return str(ULID())


def is_ulid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ULID.from_str(value)
    except ValueError:
        return False
    return True


def parse_id(value: str | None, label: str) -> str:
    """Un ULID lu, normalisé ; un nouveau s'il est absent."""
    if value is None or not value.strip():
        return new_id()
    if not is_ulid(value.strip()):
        raise InvalidInput(f"{label} n'est pas un ULID valide : {value!r}")
    return str(ULID.from_str(value.strip()))
