"""Les trames du canal du coach, et la lecture de ce qui monte.

C'est le seul endroit qui connaît la forme des messages : la §3 de la spec,
plus les évolutions de la §9 quand un réglage les active (Variants).
"""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from testbackend.catalog import Catalog

# Le protocole que la variante « hello » annonce (§9, évolution 3).
ANNOUNCED_PROTOCOL = 1


class Variants(BaseModel):
    """Les évolutions proposées du protocole (§9), chacune derrière un réglage."""

    model_config = ConfigDict(extra="forbid")

    reply_to: bool = False  # 1 : la commande désigne sa demande
    command_id: bool = False  # 2 : un identifiant de commande repris dans la Response
    hello: bool = False  # 3 : la version du protocole annoncée à la connexion
    business_code: bool = False  # 4 : un code métier dans `refused`


@dataclass(frozen=True, slots=True)
class Refusal:
    """Une commande ou un accès refusé : code HTTP, code métier, texte."""

    status: int
    code: str
    detail: str


def not_waiting(game_id: str) -> Refusal:
    return Refusal(409, "not_waiting", f"le dossier {game_id} n'attend aucune entrée")


def ambiguous(game_id: str, coach_id: str, keys: list[str]) -> Refusal:
    return Refusal(
        409,
        "ambiguous_request",
        f"la partie {game_id} attend plusieurs réponses de {coach_id} : {keys}",
    )


def stale(key: str, request_id: int) -> Refusal:
    return Refusal(
        409, "stale_request", f"la demande {key} #{request_id} n'est pas ouverte"
    )


def unreadable(errors: list[str]) -> Refusal:
    return Refusal(422, "unreadable", f"message illisible : {errors}")


def not_a_coach(game_id: str, coach_id: str) -> Refusal:
    return Refusal(403, "not_a_coach", f"{coach_id} ne joue pas le match {game_id}")


def unknown_game(game_id: str) -> Refusal:
    return Refusal(404, "unknown_game", f"le dossier {game_id} n'existe pas")


def server_error(detail: str = "erreur simulée par la doublure") -> Refusal:
    return Refusal(500, "server_error", detail)


# --- Descendant --------------------------------------------------------------


def request_frame(key: str, request_id: int, options: dict[str, Any]) -> dict[str, Any]:
    return {"type": "request", "key": key, "request_id": request_id, "options": options}


def accepted_frame(command: dict[str, Any], command_id: str | None) -> dict[str, Any]:
    frame: dict[str, Any] = {"type": "accepted", "command": command}
    if command_id is not None:
        frame["id"] = command_id
    return frame


def refused_frame(
    refusal: Refusal, variants: Variants, command_id: str | None = None
) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "type": "refused",
        "status": refusal.status,
        "detail": refusal.detail,
    }
    if variants.business_code:
        frame["code"] = refusal.code
    if command_id is not None:
        frame["id"] = command_id
    return frame


def fact_frame(seq: int, fact: dict[str, Any]) -> dict[str, Any]:
    return {"type": "fact", "seq": seq, "fact": fact}


def finished_frame(output: Any) -> dict[str, Any]:
    return {"type": "finished", "output": output}


def hello_frame() -> dict[str, Any]:
    return {"type": "hello", "protocol": ANNOUNCED_PROTOCOL}


def encode(frame: dict[str, Any]) -> str:
    return json.dumps(frame, ensure_ascii=False)


# --- Montant -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Uplink:
    """Une commande lue sur le canal, avec ce que les variantes y ajoutent."""

    command: dict[str, Any]
    command_id: str | None = None
    reply_to: str | None = None
    request_id: int | None = None

    @property
    def type(self) -> str:
        return str(self.command["type"])


def parse_uplink(raw: str, catalog: Catalog, variants: Variants) -> Uplink | Refusal:
    """La commande d'un message montant, ou son refus 422."""
    try:
        message = json.loads(raw)
    except ValueError as err:
        return unreadable([f"JSON invalide : {err}"])
    if not isinstance(message, dict):
        return unreadable(["le message doit être un objet"])
    allowed = {"command"}
    if variants.reply_to:
        allowed |= {"reply_to", "request_id"}
    if variants.command_id:
        allowed |= {"id"}
    errors = [f"champ en trop : {k}" for k in message if k not in allowed]
    if "command" not in message:
        errors.append("champ manquant : command")
    else:
        errors += catalog.check_command(message["command"])
    errors += _check_variant_fields(message)
    if errors:
        return unreadable(errors)
    return Uplink(
        command=message["command"],
        command_id=message.get("id"),
        reply_to=message.get("reply_to"),
        request_id=message.get("request_id"),
    )


def _check_variant_fields(message: dict[str, Any]) -> list[str]:
    expected = {"id": str, "reply_to": str, "request_id": int}
    return [
        f"{name} : {kind.__name__} attendu"
        for name, kind in expected.items()
        if name in message and type(message[name]) is not kind
    ]
