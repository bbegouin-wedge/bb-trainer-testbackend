"""Carte 2 — Créer un match et le rejoindre (§2 de la spec)."""

from tests.harness import GAME, HOME, STRANGER, VISITOR, Harness
from tests.joining_elements import (
    given_a_game,
    then_it_is_created,
    then_it_is_refused,
    then_only_the_game_id_is_returned,
    then_the_channel_is_refused,
    then_the_coaches_have_joined,
    then_the_ids_are_drawn,
    then_the_join_is_accepted,
    then_the_wire_reads,
    when_a_game_is_created,
    when_the_coach_connects,
    when_the_coach_reconnects,
    when_the_journal_is_read,
)

TEAM = "01JCPZ8E0000000000000Q3TN0"


def test_a_game_keeps_the_ids_it_is_given(harness: Harness) -> None:
    response = when_a_game_is_created(
        harness, "/pilot/games", game_id=GAME, home_coach=HOME, home_team=TEAM
    )
    then_it_is_created(response, game_id=GAME, home_coach=HOME, home_team=TEAM)


def test_missing_ids_are_drawn(harness: Harness) -> None:
    response = when_a_game_is_created(harness, "/pilot/games")
    then_the_ids_are_drawn(response)


def test_the_automaton_route_returns_only_the_game_id(harness: Harness) -> None:
    response = when_a_game_is_created(harness, "/games", home_coach=HOME)
    then_only_the_game_id_is_returned(response)


def test_the_same_coach_cannot_play_both_sides(harness: Harness) -> None:
    response = when_a_game_is_created(
        harness, "/games", home_coach=HOME, visitor_coach=HOME
    )
    then_it_is_refused(response, 422, "les deux coachs doivent être différents")


def test_the_same_team_cannot_play_both_sides(harness: Harness) -> None:
    response = when_a_game_is_created(
        harness, "/games", home_team=TEAM, visitor_team=TEAM
    )
    then_it_is_refused(response, 422, "les deux équipes doivent être différentes")


def test_an_id_must_be_an_ulid(harness: Harness) -> None:
    response = when_a_game_is_created(harness, "/games", home_coach="pas-un-ulid")
    then_it_is_refused(response, 422, "home_coach n'est pas un ULID valide")


def test_a_game_cannot_be_created_twice(harness: Harness) -> None:
    given_a_game(harness)
    response = when_a_game_is_created(harness, "/games", game_id=GAME)
    then_it_is_refused(response, 409, "est déjà démarré")


def test_an_unknown_game_is_refused_and_closed(harness: Harness) -> None:
    coach = when_the_coach_connects(harness)
    then_the_channel_is_refused(coach, 404, 4404, f"le dossier {GAME} n'existe pas")


def test_a_stranger_is_refused_and_closed(harness: Harness) -> None:
    given_a_game(harness)
    coach = when_the_coach_connects(harness, STRANGER)
    then_the_channel_is_refused(
        coach, 403, 4403, f"{STRANGER} ne joue pas le match {GAME}"
    )


def test_the_server_joins_on_the_first_connection(harness: Harness) -> None:
    given_a_game(harness)
    home = when_the_coach_connects(harness, HOME)
    visitor = when_the_coach_connects(harness, VISITOR)
    then_the_join_is_accepted(home, HOME)
    then_the_join_is_accepted(visitor, VISITOR)
    then_the_coaches_have_joined(harness)


def test_a_reconnection_does_not_join_again(harness: Harness) -> None:
    given_a_game(harness)
    first = harness.join(HOME)
    when_the_coach_reconnects(harness, first)
    then_the_wire_reads(
        harness,
        "home",
        "socket ouverte · admis · premier accès",
        "accepted join_game",
        "socket fermée (1000)",
        "socket ouverte · admis · reconnexion",
    )


def test_the_journal_of_an_unknown_game_is_404(harness: Harness) -> None:
    response = when_the_journal_is_read(harness, GAME)
    then_it_is_refused(response, 404, "n'existe pas")
