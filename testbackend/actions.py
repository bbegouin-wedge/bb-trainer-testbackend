"""Ce que l'opérateur, ou un scénario, fait faire à la doublure.

Une seule liste d'actions sert partout : l'API de pilotage les reçoit, la
console les envoie à cette API, un verdict en enchaîne avant son `accepted`,
et un scénario en fait ses étapes. Chacune est discriminée par `do`.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from testbackend.ids import Side

type Target = Literal["home", "visitor", "both"]


class _Action(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRequest(_Action):
    """Ouvre une demande. `to` : un coach, ou n'importe lequel (sans `to`)."""

    do: Literal["request"] = "request"
    to: Literal["home", "visitor", "any"]
    key: str = Field(min_length=1)
    options: dict[str, Any] = {}
    request_id: int | None = None  # imposé ; sinon le suivant du match
    replace: bool = True  # ferme la demande ouverte de même `key`
    twice: bool = False  # envoie la trame deux fois


class ReopenRequest(_Action):
    """Rouvre une demande ouverte sous un nouveau `request_id`."""

    do: Literal["reopen"] = "reopen"
    key: str
    options: dict[str, Any] | None = None  # fusionnées aux anciennes (ex. rejected)


class CloseRequest(_Action):
    do: Literal["close"] = "close"
    key: str


class EmitFact(_Action):
    do: Literal["fact"] = "fact"
    fact: dict[str, Any]
    to: Target = "both"
    seq: int | None = None  # imposé (trou, doublon) ; sinon le suivant
    queued: bool = False  # part avant la prochaine demande


class Finish(_Action):
    do: Literal["finish"] = "finish"
    output: Any = None


class SetPhase(_Action):
    """Le libellé de l'étape en cours, pour la console : le client n'en sait rien."""

    do: Literal["phase"] = "phase"
    label: str


class SendRaw(_Action):
    """Une trame envoyée telle quelle, sans contrôle."""

    do: Literal["raw"] = "raw"
    to: Side
    text: str


class Cut(_Action):
    """Coupe les sockets : brutalement (sans trame de fermeture) ou proprement."""

    do: Literal["cut"] = "cut"
    to: Target
    mode: Literal["abrupt", "clean"] = "abrupt"


class RefuseAccess(_Action):
    """Le prochain accès du coach : refusé (403, 404) ou arrivée en échec (500)."""

    do: Literal["refuse_access"] = "refuse_access"
    to: Side
    status: Literal[403, 404, 500]


class FrameFault(_Action):
    """La prochaine trame descendante du coach : perdue, doublée ou retardée."""

    do: Literal["frame_fault"] = "frame_fault"
    to: Side
    fault: Literal["drop", "duplicate", "delay"]
    delay_ms: int = Field(default=0, ge=0)


class Listening(_Action):
    """Arrête ou relance l'écoute des canaux ; la console reste ouverte."""

    do: Literal["listening"] = "listening"
    on: bool


type Action = Annotated[
    OpenRequest
    | ReopenRequest
    | CloseRequest
    | EmitFact
    | Finish
    | SetPhase
    | SendRaw
    | Cut
    | RefuseAccess
    | FrameFault
    | Listening,
    Field(discriminator="do"),
]


class Verdict(BaseModel):
    """Le jugement d'une commande, et ce qui part avant son `accepted`.

    like_automaton : servir l'unique demande ouverte, la rouvrir si le type de
    la commande n'est pas dans `accepts` (ce que font les étapes livrées) ;
    refuser en 409 sinon.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["like_automaton", "accept", "accept_reopen", "refuse"] = (
        "like_automaton"
    )
    refusal: Literal["not_waiting", "ambiguous", "unreadable", "server_error"] = (
        "not_waiting"
    )
    then: list[Action] = []
