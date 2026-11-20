"""Le jugement « comme automaton » : quelle demande une commande sert.

Automaton sert l'unique demande ouverte du coach (`_request_for` de son
service) ; aucune → 409, plusieurs → 409 ambigu. Avec la variante
`reply_to`, la commande désigne sa demande, et une demande qui n'est plus
ouverte est refusée comme périmée.

Ce que fait ensuite l'étape, la doublure l'imite pour un seul cas : une
commande d'un type absent de `accepts` est acceptée, et la demande rouverte
sous un nouveau numéro, comme le font les étapes livrées
(`decide_kicking_team`, `set_up_team`).
"""

from dataclasses import dataclass

from testbackend.game import Game, Request
from testbackend.ids import Side
from testbackend.protocol import (
    Refusal,
    Uplink,
    Variants,
    ambiguous,
    not_waiting,
    stale,
)


@dataclass(frozen=True, slots=True)
class Serve:
    request: Request | None
    reopen: bool = False


def served_request(
    game: Game, side: Side, uplink: Uplink, variants: Variants
) -> Request | Refusal:
    """La demande que cette commande sert, ou le refus d'automaton."""
    candidates = game.requests_for(side)
    if variants.reply_to and uplink.reply_to is not None:
        designated = [
            r
            for r in candidates
            if r.key == uplink.reply_to
            and (uplink.request_id is None or r.request_id == uplink.request_id)
        ]
        if designated:
            return designated[0]
        return stale(
            uplink.reply_to, -1 if uplink.request_id is None else uplink.request_id
        )
    match candidates:
        case []:
            return not_waiting(game.game_id)
        case [request]:
            return request
        case _:
            coach_id = game.coaches[side].coach_id
            return ambiguous(game.game_id, coach_id, [r.key for r in candidates])


def like_automaton(
    game: Game, side: Side, uplink: Uplink, variants: Variants
) -> Serve | Refusal:
    served = served_request(game, side, uplink, variants)
    if isinstance(served, Refusal):
        return served
    accepts = served.accepts
    return Serve(served, reopen=accepts is not None and uplink.type not in accepts)
