"""Le catalogue : ce qu'automaton sait recevoir, demander et annoncer.

Recopié de la §5 de la spec du protocole (`data/catalog.json`), et mis à jour
à la main quand automaton évolue. La doublure n'a pas les modèles pydantic
d'automaton : c'est ce catalogue qui décide si une commande est lisible (422)
et si un fait émis par l'opérateur est bien formé.

Un champ est décrit par un type écrit en chaîne :
    ulid, int, str, bool, any, side, square   un type simple ;
    kick|receive                              une valeur parmi celles-ci ;
    ulid[]                                    une liste ;
    ulid?                                     un champ facultatif.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ulid import ULID

from testbackend.ids import is_ulid

CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"


@dataclass(frozen=True, slots=True)
class Shape:
    """La forme d'une commande ou d'un fait : ses champs, hors `type`."""

    fields: dict[str, str]
    status: str = ""

    def check(self, payload: dict[str, Any]) -> list[str]:
        """Les erreurs de ce contenu, vide s'il est bien formé."""
        errors = [
            f"champ manquant : {name}"
            for name, spec in self.fields.items()
            if name not in payload and not spec.endswith("?")
        ]
        for name, value in payload.items():
            if name == "type":
                continue
            if name not in self.fields:
                errors.append(f"champ en trop : {name}")
            elif error := _check_value(self.fields[name].rstrip("?"), value):
                errors.append(f"{name} : {error}")
        return errors

    def example(self) -> dict[str, Any]:
        """Un contenu bien formé, pour pré-remplir un formulaire."""
        return {
            name: _example_of(spec.rstrip("?"))
            for name, spec in self.fields.items()
            if not spec.endswith("?")
        }


@dataclass(frozen=True, slots=True)
class RequestTemplate:
    """Une demande qu'une étape d'automaton sait ouvrir."""

    options: dict[str, Any]
    description: str = ""
    status: str = ""


@dataclass(frozen=True, slots=True)
class Catalog:
    commands: dict[str, Shape] = field(default_factory=dict)
    requests: dict[str, RequestTemplate] = field(default_factory=dict)
    facts: dict[str, Shape] = field(default_factory=dict)

    def check_command(self, command: Any) -> list[str]:
        return _check_typed(command, self.commands, "commande")

    def check_fact(self, fact: Any) -> list[str]:
        return _check_typed(fact, self.facts, "fait")

    def fact_example(self, type_: str) -> dict[str, Any]:
        return {"type": type_, **self.facts[type_].example()}


def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Catalog(
        commands={k: _shape(v) for k, v in raw["commands"].items()},
        requests={
            k: RequestTemplate(
                options=v["options"],
                description=v.get("description", ""),
                status=v.get("status", ""),
            )
            for k, v in raw["requests"].items()
        },
        facts={k: _shape(v) for k, v in raw["facts"].items()},
    )


def _shape(raw: dict[str, Any]) -> Shape:
    return Shape(fields=raw["fields"], status=raw.get("status", ""))


def _check_typed(payload: Any, shapes: dict[str, Shape], label: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"la {label} doit être un objet"]
    type_ = payload.get("type")
    if not isinstance(type_, str):
        return [f"la {label} n'a pas de type"]
    if type_ not in shapes:
        return [f"{label} inconnue : {type_!r}"]
    return shapes[type_].check(payload)


def _check_value(spec: str, value: Any) -> str | None:
    """L'erreur de cette valeur pour ce type, ou None si elle convient."""
    if spec.endswith("[]"):
        if not isinstance(value, list):
            return "liste attendue"
        errors = [_check_value(spec[:-2], item) for item in value]
        return next((e for e in errors if e), None)
    if "|" in spec:
        choices = spec.split("|")
        return None if value in choices else f"{value!r} n'est pas parmi {choices}"
    valid = {
        "any": lambda v: True,
        "str": lambda v: isinstance(v, str),
        "bool": lambda v: isinstance(v, bool),
        "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "ulid": is_ulid,
        "side": lambda v: v in ("home", "visitor"),
        "square": _is_square,
    }[spec](value)
    return None if valid else f"{spec} attendu, reçu {value!r}"


def _is_square(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"x", "y"}
        and all(type(value[k]) is int for k in ("x", "y"))
    )


def _example_of(spec: str) -> Any:
    if spec.endswith("[]"):
        return []
    if "|" in spec:
        return spec.split("|")[0]
    return {
        "any": None,
        "str": "",
        "bool": False,
        "int": 0,
        "ulid": str(ULID()),
        "side": "home",
        "square": {"x": 0, "y": 0},
    }[spec]
