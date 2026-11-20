"""Carte 11 — La bibliothèque : chaque scénario va au bout face à des clients
qui suivent la spec, sur le vrai serveur (carte 9 : sortie 0)."""

import pytest

from tests.live import SCENARIOS, play


@pytest.mark.parametrize("name", sorted(p.name for p in SCENARIOS.glob("*.json")))
def test_each_scenario_completes_against_reference_clients(name: str) -> None:
    code, coaches = play(SCENARIOS / name)
    assert code == 0
    assert all(c.finished for c in coaches), [c.error for c in coaches]


def test_the_reconnection_scenario_makes_the_client_come_back() -> None:
    _, (home, _) = play(SCENARIOS / "reconnexion.json")
    assert home.connections == 2


def test_a_doubled_request_is_answered_once() -> None:
    _, (home, _) = play(SCENARIOS / "demande-doublee.json")
    assert [c["type"] for c in home.sent] == ["choose_kick_off"]


def test_the_falling_server_makes_both_clients_come_back() -> None:
    _, coaches = play(SCENARIOS / "serveur-qui-tombe.json")
    assert [c.connections for c in coaches] == [2, 2]
