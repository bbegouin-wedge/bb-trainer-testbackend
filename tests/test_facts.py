"""Carte 6 — Les faits (§3, `fact`, à venir A3)."""

from tests.facts_elements import (
    KICKING,
    ROLL_OFF,
    then_it_receives_the_fact,
    then_the_facts_are,
    when_a_fact_is_emitted,
)
from tests.harness import HOME, VISITOR, Harness, request_to
from tests.requests_elements import (
    given_two_joined_coaches,
    then_it_receives,
    then_it_receives_the_request,
    then_the_action_is_refused,
)

COACH_JOINED = {"type": "coach_joined", "side": "home", "coach_id": HOME}


def test_without_relay_a_fact_stays_in_the_journal(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    when_a_fact_is_emitted(harness)
    harness.do(request_to("home"))
    then_it_receives(home, type="request")
    then_the_facts_are(
        harness, (0, "coach_joined"), (1, "coach_joined"), (2, "roll_off_won")
    )


def test_with_relay_a_fact_goes_to_its_targets(harness: Harness) -> None:
    home, visitor = given_two_joined_coaches(harness)
    harness.settings(relay_facts=True)
    when_a_fact_is_emitted(harness, to="visitor")
    when_a_fact_is_emitted(harness, KICKING)
    then_it_receives_the_fact(visitor, 2)
    then_it_receives_the_fact(visitor, 3, KICKING)
    then_it_receives_the_fact(home, 3, KICKING)


def test_an_imposed_seq_makes_a_gap_or_a_duplicate(harness: Harness) -> None:
    given_two_joined_coaches(harness)
    when_a_fact_is_emitted(harness, seq=7)
    when_a_fact_is_emitted(harness, seq=7)
    when_a_fact_is_emitted(harness)
    then_the_facts_are(
        harness,
        (0, "coach_joined"),
        (1, "coach_joined"),
        (7, "roll_off_won"),
        (7, "roll_off_won"),
        (8, "roll_off_won"),
    )


def test_a_queued_fact_leaves_before_the_next_request(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.settings(relay_facts=True)
    when_a_fact_is_emitted(harness, queued=True)
    then_the_facts_are(harness, (0, "coach_joined"), (1, "coach_joined"))
    harness.do(request_to("home"))
    then_it_receives_the_fact(home, 2)
    then_it_receives_the_request(home, "kick_off_choice", 0)


def test_a_queued_fact_leaves_before_the_end(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    harness.settings(relay_facts=True)
    when_a_fact_is_emitted(harness, queued=True)
    harness.do({"do": "finish"})
    then_it_receives_the_fact(home, 2)
    then_it_receives(home, type="finished", output=None)


def test_every_connection_catches_up_the_facts_first(harness: Harness) -> None:
    harness.create_game()
    harness.settings(relay_facts=True)
    when_a_fact_is_emitted(harness)
    home = harness.connect(HOME)
    then_it_receives_the_fact(home, 0)
    then_it_receives_the_fact(home, 1, COACH_JOINED)
    then_it_receives(home, type="accepted")
    harness.do(request_to("home"))
    then_it_receives(home, type="request")
    home.ws.close()
    again = harness.connect(HOME)
    then_it_receives_the_fact(again, 0)
    then_it_receives_the_fact(again, 1, COACH_JOINED)
    then_it_receives(again, type="request", key="kick_off_choice")


def test_a_malformed_fact_is_422(harness: Harness) -> None:
    given_two_joined_coaches(harness)
    then_the_action_is_refused(
        harness,
        {"do": "fact", "fact": {"type": "roll_off_won", "side": "ici"}},
        422,
        "side attendu",
    )
    then_the_action_is_refused(
        harness, {"do": "fact", "fact": {"type": "inconnu"}}, 422, "fait inconnu"
    )


def test_the_joined_coach_is_a_fact(harness: Harness) -> None:
    given_two_joined_coaches(harness)
    assert harness.journal()["facts"][1]["fact"] == {
        "type": "coach_joined",
        "side": "visitor",
        "coach_id": VISITOR,
    }
    assert ROLL_OFF["side"] == "home"
