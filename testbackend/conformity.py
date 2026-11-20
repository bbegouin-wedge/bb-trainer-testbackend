"""La conformité du client : les règles de la §6 que le serveur peut observer.

Un écart est noté au moment où il se produit (Deviation dans le match). Une
règle est « éprouvée » dès que le client a eu l'occasion de l'enfreindre :
sans cela, son statut reste « non éprouvée ».

R7 (se reconnecter après une coupure) se juge au temps : une coupure
provoquée sans reconnexion dans le délai est un écart, constaté à la
reconnexion tardive, ou à la lecture du rapport si elle n'a pas eu lieu.
"""

from dataclasses import dataclass
from typing import Literal

from testbackend.game import Deviation, Game
from testbackend.ids import Side

type Status = Literal["ok", "ko", "na"]


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    title: str
    hint: str
    observable: bool = True


RULES: tuple[Rule, ...] = (
    Rule(
        "R2",
        "Une commande à la fois",
        "pas de commande avant la Response de la précédente",
    ),
    Rule(
        "R3",
        "Ne répondre qu'à une demande ouverte",
        "une demande de ce coach, dont `accepts` contient le type",
    ),
    Rule("422", "Messages lisibles", "JSON valide, commande connue, champs exacts"),
    Rule(
        "JOIN",
        "Pas de join_game envoyé",
        "le serveur le traite lui-même à la connexion",
    ),
    Rule("R7", "Se reconnecter après une coupure", "dans le délai réglé"),
    Rule(
        "R4",
        "Ignorer une demande reçue deux fois",
        "non observable côté serveur : voir le journal de bbTrainer",
        observable=False,
    ),
)


@dataclass(frozen=True, slots=True)
class RuleReport:
    rule: Rule
    status: Status
    deviations: list[Deviation]


def note(game: Game, rule: str, side: Side, at: float, detail: str) -> None:
    game.deviations.append(Deviation(rule, side, at, detail))


def report(game: Game, now: float, reconnect_timeout: float) -> list[RuleReport]:
    late = [
        Deviation("R7", c.side, c.cut_at, "pas reconnecté après la coupure")
        for c in game.coaches.values()
        if c.cut_at is not None and now - c.cut_at > reconnect_timeout
    ]
    deviations = game.deviations + late
    reports = []
    for rule in RULES:
        mine = [d for d in deviations if d.rule == rule.id]
        status: Status = "ko" if mine else "ok" if rule.id in game.exercised else "na"
        reports.append(RuleReport(rule, status, mine))
    return reports
