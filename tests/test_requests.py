"""Carte 3 — Les demandes et les commandes (§3, §4, §7 de la spec)."""

from tests.harness import HOME, VISITOR, Harness, request_to
from tests.requests_elements import (
    ambiguous,
    given_a_kick_off_request,
    given_two_joined_coaches,
    not_waiting,
    then_it_is_accepted,
    then_it_is_refused,
    then_it_receives,
    then_it_receives_the_request,
    then_the_action_is_refused,
    then_the_frame_was_lost,
    then_the_open_requests_are,
    then_the_wire_warns,
    when_the_coach_sends,
    when_the_operator_opens,
)

# --- Ouvrir une demande -------------------------------------------------------


def test_a_request_goes_to_its_coach_only(harness: Harness) -> None:
    home, visitor = given_two_joined_coaches(harness)
    when_the_operator_opens(harness, request_to("visitor"))
    then_it_receives_the_request(visitor, "kick_off_choice", 0, VISITOR)
    when_the_operator_opens(harness, request_to("home", key="other"))
    then_it_receives_the_request(home, "other", 1)


def test_a_request_for_any_coach_goes_to_both_without_to(harness: Harness) -> None:
    home, visitor = given_two_joined_coaches(harness)
    when_the_operator_opens(
        harness, request_to("any", options={"to": "coach", "accepts": ["x"]})
    )
    then_it_receives_the_request(home, "kick_off_choice", 0, None, accepts=["x"])
    then_it_receives_the_request(visitor, "kick_off_choice", 0, None, accepts=["x"])


def test_an_imposed_request_id_moves_the_counter(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    when_the_operator_opens(harness, request_to("home", request_id=7))
    then_it_receives_the_request(home, "kick_off_choice", 7)
    when_the_operator_opens(harness, request_to("home"))
    then_it_receives_the_request(home, "kick_off_choice", 8)
    then_the_open_requests_are(harness, ("kick_off_choice", 8))


def test_a_request_can_be_kept_beside_the_previous_and_sent_twice(
    harness: Harness,
) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_operator_opens(harness, request_to("home", replace=False, twice=True))
    then_it_receives_the_request(home, "kick_off_choice", 1)
    then_it_receives_the_request(home, "kick_off_choice", 1)
    then_the_open_requests_are(harness, ("kick_off_choice", 0), ("kick_off_choice", 1))


def test_a_reopened_request_merges_its_options(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_operator_opens(
        harness,
        {"do": "reopen", "key": "kick_off_choice", "options": {"rejected": ["non"]}},
    )
    then_it_receives_the_request(
        home,
        "kick_off_choice",
        1,
        accepts=["choose_kick_off"],
        choices=["kick", "receive"],
        rejected=["non"],
    )


def test_a_closed_request_is_no_longer_served(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_operator_opens(harness, {"do": "close", "key": "kick_off_choice"})
    when_the_coach_sends(home)
    then_it_is_refused(home, 409, not_waiting())


def test_only_an_open_request_can_be_reopened_or_closed(harness: Harness) -> None:
    given_two_joined_coaches(harness)
    then_the_action_is_refused(
        harness,
        {"do": "reopen", "key": "absente"},
        409,
        "aucune demande absente ouverte",
    )
    then_the_action_is_refused(
        harness,
        {"do": "close", "key": "absente"},
        409,
        "aucune demande absente ouverte",
    )


def test_an_action_on_an_unknown_game_is_404(harness: Harness) -> None:
    then_the_action_is_refused(harness, request_to("home"), 404, "n'existe pas")


def test_a_request_to_an_absent_coach_is_lost_then_caught_up(harness: Harness) -> None:
    harness.create_game()
    when_the_operator_opens(harness, request_to("home"))
    then_the_frame_was_lost(harness, "home", "request kick_off_choice #0")
    harness.join(HOME).ws.close()
    home = harness.connect(HOME)
    then_it_receives_the_request(home, "kick_off_choice", 0)


def test_the_catch_up_can_be_turned_off(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    harness.settings(catch_up_requests=False)
    home.ws.close()
    home = harness.connect(HOME)
    when_the_coach_sends(home)
    then_it_is_accepted(home)


def test_a_request_without_recipient_is_not_sent(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_operator_opens(
        harness,
        {
            "do": "reopen",
            "key": "kick_off_choice",
            "options": {"to": "management_system"},
        },
    )
    then_the_wire_warns(harness, "demande kick_off_choice sans destinataire")


# --- Juger une commande, comme automaton -------------------------------------------


def test_a_command_serves_the_open_request(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_coach_sends(home)
    then_it_is_accepted(home)
    then_the_open_requests_are(harness)


def test_a_command_without_request_is_409(harness: Harness) -> None:
    _, visitor = given_two_joined_coaches(harness)
    when_the_coach_sends(visitor)
    then_it_is_refused(visitor, 409, not_waiting())


def test_two_open_requests_make_the_command_ambiguous(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    given_a_kick_off_request(harness, home, key="other")
    when_the_coach_sends(home)
    then_it_is_refused(home, 409, ambiguous())


def test_a_command_of_another_type_is_accepted_and_the_request_reopened(
    harness: Harness,
) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_coach_sends(home, {"type": "end_set_up"})
    then_it_receives_the_request(home, "kick_off_choice", 1)
    then_it_is_accepted(home, {"type": "end_set_up"})


def test_unreadable_messages_are_422(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    cases = {
        "pas du json": "JSON invalide",
        "[]": "le message doit être un objet",
        "{}": "champ manquant : command",
        '{"command": 3}': "la commande doit être un objet",
        '{"command": {}}': "la commande n'a pas de type",
        '{"command": {"type": "fly"}}': "commande inconnue : 'fly'",
        '{"command": {"type": "choose_kick_off"}}': "champ manquant : choice",
        '{"command": {"type": "choose_kick_off", "choice": "recieve"}}': "'recieve' n'est pas parmi",
        '{"command": {"type": "end_set_up", "x": 1}}': "champ en trop : x",
        '{"command": {"type": "end_set_up"}, "reply_to": "k"}': "champ en trop : reply_to",
    }
    for raw, detail in cases.items():
        home.raw(raw)
        then_it_is_refused(home, 422, detail)


def test_command_fields_are_typed(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    cases = {
        '{"type": "join_game", "coach_id": "x"}': "ulid attendu",
        '{"type": "place_player", "player_id": "01JCQ4K2H8P5S7D3F9A1E6C0QM", "square": {"x": 1}}': "square attendu",
    }
    for command, detail in cases.items():
        home.raw(f'{{"command": {command}}}')
        then_it_is_refused(home, 422, detail)


def test_commands_are_answered_in_order(harness: Harness) -> None:
    home, _ = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_coach_sends(home)
    when_the_coach_sends(home)
    then_it_is_accepted(home)
    then_it_is_refused(home, 409, not_waiting())


# --- La fin du match ------------------------------------------------------------------


def test_the_end_goes_to_both_coaches_and_closes_the_requests(harness: Harness) -> None:
    home, visitor = given_two_joined_coaches(harness)
    given_a_kick_off_request(harness, home)
    when_the_operator_opens(harness, {"do": "finish", "output": {"score": [1, 0]}})
    then_it_receives(home, type="finished", output={"score": [1, 0]})
    then_it_receives(visitor, type="finished", output={"score": [1, 0]})
    then_the_open_requests_are(harness)
