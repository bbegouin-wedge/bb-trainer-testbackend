"""L'état d'un match dans la doublure, en mémoire.

Sans moteur : pas de pile, pas de règles. Un match, c'est deux coachs, les
demandes ouvertes, les faits émis, le fil des trames, les commandes en
attente de jugement et les écarts du client. Ce module n'a aucune entrée ni
sortie : le service (backend) le fait vivre.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from testbackend.actions import Action
from testbackend.ids import SIDES, Side
from testbackend.protocol import Uplink

type Direction = Literal["down", "up", "sys"]
type Level = Literal["info", "ok", "warn", "error"]


@dataclass(slots=True)
class Coach:
    side: Side
    coach_id: str
    team_id: str
    joined: bool = False
    sockets: int = 0
    cut_at: float | None = None  # coupure provoquée, en attente de reconnexion

    @property
    def connected(self) -> bool:
        return self.sockets > 0


@dataclass(frozen=True, slots=True)
class Request:
    key: str
    request_id: int
    options: dict[str, Any]

    def recipients(self, game: "Game") -> list[Side]:
        """Les coachs qui peuvent la servir, comme `recipient_of` d'automaton :
        sans `to`, n'importe lequel ; `to: coach`, celui de `coach_id`."""
        match self.options:
            case {"to": "coach", "coach_id": str(coach_id)}:
                side = game.side_of(coach_id)
                return [side] if side else []
            case {"to": _}:
                return []
            case _:
                return list(SIDES)

    @property
    def accepts(self) -> list[str] | None:
        accepts = self.options.get("accepts")
        return [str(a) for a in accepts] if isinstance(accepts, list) else None


@dataclass(frozen=True, slots=True)
class Fact:
    seq: int
    fact: dict[str, Any]


@dataclass(frozen=True, slots=True)
class QueuedFact:
    fact: dict[str, Any]
    targets: list[Side]
    seq: int | None


@dataclass(frozen=True, slots=True)
class WireEntry:
    at: float
    side: Side | None
    direction: Direction
    kind: str
    text: str = ""
    note: str = ""
    level: Level = "info"


@dataclass(slots=True)
class Pending:
    """Une commande lue, en attente de jugement (manuel ou par scénario)."""

    number: int
    side: Side
    uplink: Uplink
    received_at: float
    staged: list[Action] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Deviation:
    rule: str
    side: Side
    at: float
    detail: str


@dataclass(slots=True)
class Game:
    game_id: str
    coaches: dict[Side, Coach]
    requests: list[Request] = field(default_factory=list)
    next_request_id: int = 0
    facts: list[Fact] = field(default_factory=list)
    queued_facts: list[QueuedFact] = field(default_factory=list)
    phase: str = ""
    finished: bool = False
    wire: list[WireEntry] = field(default_factory=list)
    pending: list[Pending] = field(default_factory=list)
    next_pending: int = 0
    in_flight: dict[Side, int] = field(default_factory=lambda: dict.fromkeys(SIDES, 0))
    deviations: list[Deviation] = field(default_factory=list)
    exercised: set[str] = field(default_factory=set)
    # Les gestes du match, en étapes de scénario : connexions, commandes jugées,
    # actions de l'opérateur. C'est « le fil en scénario » de la console.
    script: list[dict[str, Any]] = field(default_factory=list)
    version: int = 0

    def side_of(self, coach_id: str) -> Side | None:
        return next(
            (s for s, c in self.coaches.items() if c.coach_id == coach_id), None
        )

    def requests_for(self, side: Side) -> list[Request]:
        return [r for r in self.requests if side in r.recipients(self)]

    def find_request(self, key: str) -> Request | None:
        return next((r for r in self.requests if r.key == key), None)

    def add_request(
        self, key: str, options: dict[str, Any], request_id: int | None
    ) -> Request:
        if request_id is None:
            request_id = self.next_request_id
        self.next_request_id = max(self.next_request_id, request_id + 1)
        request = Request(key, request_id, options)
        self.requests.append(request)
        return request

    def close_request(self, request: Request) -> None:
        self.requests.remove(request)

    def add_fact(self, fact: dict[str, Any], seq: int | None) -> Fact:
        """Range un fait ; `seq` imposé peut faire un trou ou un doublon."""
        if seq is None:
            seq = max((f.seq for f in self.facts), default=-1) + 1
        added = Fact(seq, fact)
        self.facts.append(added)
        return added

    def add_pending(self, side: Side, uplink: Uplink, at: float) -> Pending:
        pending = Pending(self.next_pending, side, uplink, at)
        self.next_pending += 1
        self.pending.append(pending)
        return pending

    def find_pending(self, number: int) -> Pending | None:
        return next((p for p in self.pending if p.number == number), None)

    def first_pending(self, side: Side) -> Pending | None:
        return next((p for p in self.pending if p.side == side), None)
