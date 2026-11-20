"""Carte 12 — Les variantes du protocole (§9)."""

from tests.harness import HOME, KICK, Harness, request_to
from tests.requests_elements import (
    given_a_kick_off_request,
    given_two_joined_coaches,
    then_it_is_refused,
    then_it_receives,
)


def test_hello_announces_the_protocol_first(harness: Harness) -> None:
    harness.create_game()
    harness.settings(variants={"hello": True})
    home = harness.connect(HOME)
    then_it_receives(home, type="hello", protocol=1)
    then_it_receives(home, type="accepted")


def test_the_command_id_comes_back_in_the_response(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.settings(variants={"command_id": True})
    home.command(KICK, id="c-1")
    then_it_receives(home, type="refused", id="c-1")
    given_a_kick_off_request(harness, home)
    home.command(KICK, id="c-2")
    then_it_receives(home, type="accepted", id="c-2")


def test_the_business_code_tells_the_two_409_apart(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.settings(variants={"business_code": True})
    home.command(KICK)
    then_it_receives(home, type="refused", status=409, code="not_waiting")


def test_reply_to_designates_the_request(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.settings(variants={"reply_to": True, "business_code": True})
    given_a_kick_off_request(harness, home)
    given_a_kick_off_request(harness, home, key="other")
    home.command(KICK, reply_to="kick_off_choice", request_id=7)
    then_it_receives(home, type="refused", code="stale_request")
    home.command(KICK, reply_to="other")
    then_it_receives(home, type="accepted")
    home.command(KICK, reply_to="kick_off_choice", request_id=0)
    then_it_receives(home, type="accepted")
    home.command(KICK, reply_to="kick_off_choice")
    then_it_receives(
        home, type="refused", detail="la demande kick_off_choice #-1 n'est pas ouverte"
    )


def test_variant_fields_are_typed(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.settings(variants={"reply_to": True, "command_id": True})
    home.command(KICK, id=3, request_id="7")
    then_it_is_refused(home, 422, "id : str attendu")
    harness.do(request_to("home"))
