"""Carte 8 — La conformité du client (§6)."""

from tests.conformity_elements import then_the_deviation_reads, then_the_rules_read
from tests.console_elements import given_a_command_to_judge, given_a_manual_judge
from tests.harness import HOME, KICK, Harness, request_to
from tests.requests_elements import (
    given_a_kick_off_request,
    given_two_joined_coaches,
    then_it_is_accepted,
    then_it_is_refused,
    then_it_receives,
)


def test_untested_rules_are_not_exercised(harness: Harness) -> None:
    given_two_joined_coaches(harness)
    then_the_rules_read(
        harness, R2="na", R3="na", R422="na", JOIN="na", R7="na", R4="na"
    )


def test_a_well_behaved_client_has_no_deviation(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    home.command(KICK)
    then_it_is_accepted(home)
    then_the_rules_read(harness, R2="ok", R3="ok", R422="ok", JOIN="ok", R4="na")


def test_r2_two_commands_in_flight(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    number = given_a_command_to_judge(harness, home)
    home.command(KICK)
    harness.judge(number, kind="accept")
    then_it_is_accepted(home)
    harness.judge(harness.wait_pending()[0]["number"], kind="like_automaton")
    then_it_is_refused(home, 409, "n'attend aucune entrée")
    then_the_deviation_reads(
        harness, "R2", "home", "commande envoyée avant la Response de la précédente"
    )


def test_r3_a_command_without_request_or_out_of_accepts(harness: Harness) -> None:
    home, visitor = given_two_joined_coaches(harness)
    visitor.command(KICK)
    then_it_is_refused(visitor, 409, "n'attend aucune entrée")
    given_a_kick_off_request(harness, home)
    home.command({"type": "end_set_up"})
    then_it_receives(home, type="request")
    then_it_is_accepted(home, {"type": "end_set_up"})
    then_the_deviation_reads(
        harness, "R3", "visitor", "choose_kick_off sans demande ouverte"
    )
    then_the_deviation_reads(harness, "R3", "home", "end_set_up absent de accepts")


def test_unreadable_and_join_game_are_deviations(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    home.raw("{")
    then_it_is_refused(home, 422, "JSON invalide")
    home.command({"type": "join_game", "coach_id": HOME})
    then_it_is_refused(home, 409, "n'attend aucune entrée")
    then_the_rules_read(harness, R422="ko", JOIN="ko")


def test_r7_a_timely_reconnection(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.do({"do": "cut", "to": "home", "mode": "clean"})
    assert home.closed_with() == 1000
    harness.clock.advance(2)
    harness.connect(HOME)
    harness.do(request_to("home"))
    then_the_rules_read(harness, R7="ok")


def test_r7_a_late_reconnection(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.do({"do": "cut", "to": "home"})
    assert home.closed_with() == 1006
    harness.clock.advance(6)
    harness.connect(HOME)
    harness.do(request_to("home"))
    then_the_deviation_reads(harness, "R7", "home", "reconnecté après 6.0 s")


def test_r7_no_reconnection(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.do({"do": "cut", "to": "home"})
    assert home.closed_with() == 1006
    then_the_rules_read(harness, R7="ok")
    harness.clock.advance(10)
    then_the_deviation_reads(harness, "R7", "home", "pas reconnecté après la coupure")
