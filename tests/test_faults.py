"""Carte 7 — Les pannes."""

from tests.faults_elements import (
    then_it_reads_text,
    then_the_socket_closes_with,
    then_the_wire_notes,
    when_the_operator_arms,
)
from tests.harness import HOME, VISITOR, Harness, request_to
from tests.joining_elements import (
    then_the_channel_is_refused,
    then_the_join_is_accepted,
)
from tests.requests_elements import (
    given_two_joined_coaches,
    then_it_is_refused,
    then_it_receives,
    then_it_receives_the_request,
    then_the_action_is_refused,
    then_the_wire_warns,
)


def test_a_clean_cut_closes_with_1000(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    when_the_operator_arms(harness, do="cut", to="home", mode="clean")
    then_the_socket_closes_with(home, 1000)


def test_an_abrupt_cut_closes_both_with_1006(harness: Harness) -> None:
    home, visitor = given_two_joined_coaches(harness)
    when_the_operator_arms(harness, do="cut", to="both")
    then_the_socket_closes_with(home, 1006)
    then_the_socket_closes_with(visitor, 1006)


def test_cutting_an_absent_coach_is_noted(harness: Harness) -> None:
    harness.create_game()
    when_the_operator_arms(harness, do="cut", to="home")
    then_the_wire_warns(harness, "coupure : aucune socket ouverte")


def test_the_next_access_can_be_refused_once(harness: Harness) -> None:
    harness.create_game()
    when_the_operator_arms(harness, do="refuse_access", to="home", status=403)
    then_the_channel_is_refused(
        harness.connect(HOME), 403, 4403, "ne joue pas le match"
    )
    when_the_operator_arms(harness, do="refuse_access", to="home", status=404)
    then_the_channel_is_refused(harness.connect(HOME), 404, 4404, "n'existe pas")
    then_the_join_is_accepted(harness.connect(HOME))


def test_a_failed_arrival_keeps_the_socket_open_without_joining(
    harness: Harness,
) -> None:
    harness.create_game()
    when_the_operator_arms(harness, do="refuse_access", to="visitor", status=500)
    visitor = harness.connect(VISITOR)
    then_it_is_refused(visitor, 500, "erreur simulée")
    visitor.command({"type": "choose_kick_off", "choice": "kick"})
    then_it_is_refused(visitor, 409, "n'attend aucune entrée")
    visitor.ws.close()
    then_the_join_is_accepted(harness.connect(VISITOR), VISITOR)


def test_the_next_frame_can_be_dropped_doubled_or_delayed(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    when_the_operator_arms(harness, do="frame_fault", to="home", fault="drop")
    harness.do(request_to("home"))
    then_the_wire_notes(harness, "home", "request kick_off_choice #0", "perdue : panne")
    when_the_operator_arms(harness, do="frame_fault", to="home", fault="duplicate")
    harness.do(request_to("home"))
    then_it_receives_the_request(home, "kick_off_choice", 1)
    then_it_receives_the_request(home, "kick_off_choice", 1)
    when_the_operator_arms(
        harness, do="frame_fault", to="home", fault="delay", delay_ms=20
    )
    harness.do(request_to("home"))
    then_it_receives_the_request(home, "kick_off_choice", 2)
    then_the_wire_notes(
        harness, "home", "request kick_off_choice #2", "panne : retardée de 20 ms"
    )


def test_a_raw_frame_is_sent_as_is(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    when_the_operator_arms(harness, do="raw", to="home", text="pas du json")
    then_it_reads_text(home, "pas du json")


def test_listening_needs_a_listener(harness: Harness) -> None:
    harness.create_game()
    then_the_action_is_refused(
        harness, {"do": "listening", "on": False}, 409, "ne se pilote pas ici"
    )


def test_a_cut_coach_can_come_back(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.do(request_to("home"))
    then_it_receives(home, type="request")
    when_the_operator_arms(harness, do="cut", to="home", mode="clean")
    then_the_socket_closes_with(home, 1000)
    then_it_receives_the_request(harness.connect(HOME), "kick_off_choice", 0)
