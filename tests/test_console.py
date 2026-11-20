"""Cartes 4 et 5 — La console, en lecture et aux commandes."""

from tests.console_elements import (
    given_a_command_to_judge,
    given_a_manual_judge,
    then_a_push_shows,
    then_it_redirects_to,
    then_it_shows,
    then_nothing_waits,
    then_the_status_is,
    when_the_operator_judges,
    when_the_operator_stages,
    when_the_operator_watches,
    when_the_page_is_read,
)
from tests.harness import GAME, HOME, Harness, request_to
from tests.requests_elements import (
    not_waiting,
    then_it_is_accepted,
    then_it_is_refused,
    then_it_receives,
    then_it_receives_the_request,
)

# --- En lecture ---------------------------------------------------------------------


def test_the_console_without_game_invites_to_create_one(harness: Harness) -> None:
    response = when_the_page_is_read(harness, "/")
    then_it_shows(response, "Aucun match", "+ Nouveau")


def test_the_console_opens_the_latest_game(harness: Harness) -> None:
    harness.create_game()
    response = when_the_page_is_read(harness, "/")
    then_it_redirects_to(response, f"/ui/games/{GAME}")


def test_the_page_shows_the_game_and_its_channels(harness: Harness) -> None:
    harness.create_game()
    harness.do({"do": "phase", "label": "Avant-match"})
    response = when_the_page_is_read(harness, f"/ui/games/{GAME}")
    then_it_shows(
        response,
        f"ws://127.0.0.1:8000/games/{GAME}/coaches/{HOME}/ws",
        "Avant-match",
        "match créé",
    )


def test_the_page_of_an_unknown_game_is_404(harness: Harness) -> None:
    response = when_the_page_is_read(harness, f"/ui/games/{GAME}")
    then_the_status_is(response, 404, "n'existe pas")


def test_the_static_files_are_served(harness: Harness) -> None:
    response = when_the_page_is_read(harness, "/ui/static/console.js")
    then_it_shows(response, "json-body")


def test_the_watcher_is_pushed_every_change(harness: Harness) -> None:
    harness.create_game()
    watcher = when_the_operator_watches(harness)
    then_a_push_shows(watcher, 'id="wire" hx-swap-oob="true"', "match créé")
    harness.join(HOME)
    then_a_push_shows(watcher, "accepted join_game")


def test_the_page_shows_what_waits(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    given_a_command_to_judge(harness, home)
    harness.do(
        {"do": "fact", "fact": {"type": "roll_off_won", "side": "home"}, "queued": True}
    )
    harness.settings(relay_facts=True, variants={"hello": True})
    response = when_the_page_is_read(harness, f"/ui/games/{GAME}")
    then_it_shows(
        response,
        "Commande n°0 à juger",
        "en file",
        "relayés",
        "+ variantes",
        "avant l'accepted de la commande n°0",
    )


# --- Le jugement manuel ------------------------------------------------------------------


def test_a_command_waits_for_the_operator(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    number = given_a_command_to_judge(harness, home)
    when_the_operator_judges(harness, number, kind="like_automaton")
    then_it_is_accepted(home)
    then_nothing_waits(harness)


def test_accept_closes_and_accept_reopen_reopens(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    when_the_operator_judges(
        harness, given_a_command_to_judge(harness, home), kind="accept_reopen"
    )
    then_it_receives_the_request(home, "kick_off_choice", 1)
    then_it_is_accepted(home)
    when_the_operator_judges(
        harness, given_a_command_to_judge(harness, home), kind="accept"
    )
    then_it_is_accepted(home)
    when_the_operator_judges(
        harness, given_a_command_to_judge(harness, home), kind="accept"
    )
    then_it_is_accepted(home)


def test_the_operator_refuses_with_any_code(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    for refusal, status, detail in [
        ("not_waiting", 409, not_waiting()),
        ("ambiguous", 409, "attend plusieurs réponses"),
        ("unreadable", 422, "refusé par l'opérateur"),
        ("server_error", 500, "erreur simulée"),
    ]:
        number = given_a_command_to_judge(harness, home)
        when_the_operator_judges(harness, number, kind="refuse", refusal=refusal)
        then_it_is_refused(home, status, detail)


def test_staged_actions_leave_before_the_accepted(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    harness.settings(relay_facts=True)
    number = given_a_command_to_judge(harness, home)
    when_the_operator_stages(
        harness,
        number,
        {"do": "fact", "fact": {"type": "kicking_team_chosen", "side": "home"}},
    )
    when_the_operator_judges(
        harness,
        number,
        kind="accept",
        then=[request_to("home", key="set_up", options={})],
    )
    then_it_receives(
        home, type="fact", fact={"type": "kicking_team_chosen", "side": "home"}
    )
    then_it_receives(home, type="request", key="set_up")
    then_it_is_accepted(home)


def test_only_a_waiting_command_can_be_judged_or_staged(harness: Harness) -> None:
    given_a_manual_judge(harness)
    then_the_status_is(
        when_the_operator_judges(harness, 9), 409, "aucune commande n°9 à juger"
    )
    then_the_status_is(
        when_the_operator_stages(harness, 9, {"do": "finish"}),
        409,
        "aucune commande n°9 à juger",
    )


def test_a_waiting_command_is_dropped_when_its_coach_leaves(harness: Harness) -> None:
    home, _ = given_a_manual_judge(harness)
    given_a_command_to_judge(harness, home)
    home.ws.close()
    then_it_receives(harness.connect(HOME), type="request", key="kick_off_choice")
    then_nothing_waits(harness)
    assert "commande n°0 abandonnée : socket fermée" in harness.wire("home")


def test_invalid_settings_are_422(harness: Harness) -> None:
    response = harness.client.patch("/pilot/settings", json={"judge": "au hasard"})
    then_the_status_is(response, 422, "réglages invalides")


def test_the_settings_and_catalog_can_be_read(harness: Harness) -> None:
    then_it_shows(harness.client.get("/pilot/settings"), '"judge":"auto"')
    then_it_shows(
        harness.client.get("/pilot/catalog"),
        "choose_kick_off",
        "kick_off_choice",
        "kicking_team_chosen",
    )


def test_games_can_be_listed_and_read(harness: Harness) -> None:
    harness.create_game()
    then_it_shows(harness.client.get("/pilot/games"), GAME)
    then_it_shows(harness.client.get(f"/pilot/games/{GAME}"), '"phase":""')
