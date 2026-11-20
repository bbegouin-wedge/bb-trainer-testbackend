"""Les cas limites des modules, hors des parcours des cartes."""

import asyncio

from testbackend.backend import Backend, Channel
from testbackend.catalog import Shape, load_catalog
from testbackend.scenario.runner import Runner
from tests.harness import HOME, Harness
from tests.requests_elements import given_two_joined_coaches, then_it_receives

CATALOG = load_catalog()


def test_list_fields_are_checked_item_by_item() -> None:
    shape = CATALOG.facts["team_fetched"]
    assert "players : liste attendue" in shape.check({"players": "x"})
    assert "players : ulid attendu, reçu 3" in shape.check({"players": [3]})
    assert Shape(
        {"n": "int", "ok": "bool", "s": "str", "l": "ulid[]", "o": "int?"}
    ).example() == {"n": 0, "ok": False, "s": "", "l": []}
    assert Shape({"n": "int", "ok": "bool"}).check({"n": True, "ok": 1}) == [
        "n : int attendu, reçu True",
        "ok : bool attendu, reçu 1",
    ]


def test_a_coach_with_two_sockets_stays_connected_when_one_closes(
    harness: Harness,
) -> None:
    home, _ = given_two_joined_coaches(harness)
    second = harness.connect(HOME)
    home.ws.close()
    harness.do({"do": "request", "to": "home", "key": "k", "options": {}})
    then_it_receives(second, type="request", key="k")
    assert harness.journal()["coaches"]["home"]["connected"]


def test_draining_gives_up_on_a_blocked_socket() -> None:
    async def scenario() -> None:
        backend = Backend()
        game = backend.create_game()
        channel = Channel()
        backend.open_channel(game.game_id, "home", channel, fail_arrival=False)
        await backend.drain(
            timeout=0.01
        )  # personne ne vide la file : on n'attend pas plus
        assert not channel.outbox.empty()

    asyncio.run(scenario())


def test_waiting_without_scenario_returns_the_idle_state() -> None:
    async def scenario() -> str:
        return (await Runner(Backend()).wait()).status

    assert asyncio.run(scenario()) == "idle"
