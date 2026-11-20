"""Cartes 9 et 10 — Le lecteur de scénarios, ses routes et sa page."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from testbackend.errors import InvalidInput
from testbackend.scenario.model import (
    ScenarioError,
    derive,
    load,
    parse_step,
    substitute,
)
from tests.harness import GAME, HOME, KICK, VISITOR, Harness, build_harness, request_to
from tests.requests_elements import (
    then_it_is_accepted,
    then_it_is_refused,
    then_it_receives,
)
from tests.scenario import attempt, then_it_fails_with
from tests.scenarios_elements import (
    IDS,
    given_a_scenario,
    then_it_failed_with,
    then_the_state_becomes,
    when_it_is_controlled,
    when_it_runs,
)

REQUEST = request_to("home")
JOIN_HOME = {"wait": "connect", "coach": "home", "timeout": 5}


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def harness(directory: Path) -> Iterator[Harness]:
    harness, stack = build_harness(directory)
    with stack, harness.stack:
        yield harness


# --- Le lecteur ----------------------------------------------------------------------


def test_a_scenario_plays_a_whole_exchange(harness: Harness, directory: Path) -> None:
    file = given_a_scenario(
        directory,
        [
            JOIN_HOME,
            REQUEST,
            {
                "wait": "command",
                "coach": "home",
                "type": "choose_kick_off",
                "bind": {"choice": "c"},
                "set": {
                    "side": {
                        "from": "$c",
                        "map": {"kick": "home", "receive": "visitor"},
                    }
                },
                "judge": {"then": [{"do": "phase", "label": "$c par $side"}]},
            },
            {"set": {"done": True}},
            {"do": "finish"},
        ],
        settings={"relay_facts": True},
    )
    then_it_is_created = when_it_runs(harness, file)
    assert then_it_is_created.json() == {"game_id": GAME}
    home = harness.connect(HOME)
    then_it_receives(home, type="fact")
    then_it_receives(home, type="accepted")
    then_it_receives(home, type="request")
    home.command(KICK)
    then_it_is_accepted(home)
    then_it_receives(home, type="finished")
    state = then_the_state_becomes(harness, "done")
    assert state["variables"] == {"c": "kick", "side": "home", "done": True}
    assert harness.journal()["phase"] == "kick par home"
    assert harness.client.get("/pilot/settings").json()["judge"] == "auto"


def test_step_by_step_then_resume(harness: Harness, directory: Path) -> None:
    file = given_a_scenario(
        directory,
        [
            {"do": "phase", "label": "un"},
            {"do": "phase", "label": "deux"},
            {"do": "phase", "label": "trois"},
        ],
    )
    harness.create_game()
    when_it_runs(harness, file, game_id=GAME, step_mode=True)
    assert then_the_state_becomes(harness, "paused")["index"] == 0
    when_it_is_controlled(harness, "step")
    assert then_the_state_becomes(harness, "paused")["index"] in (0, 1)
    when_it_is_controlled(harness, "resume")
    then_the_state_becomes(harness, "done")
    assert harness.journal()["phase"] == "trois"


def test_a_running_scenario_can_be_paused_and_stopped(
    harness: Harness, directory: Path
) -> None:
    file = given_a_scenario(directory, [JOIN_HOME, {"do": "phase", "label": "après"}])
    when_it_runs(harness, file)
    then_the_state_becomes(harness, "running")
    assert when_it_is_controlled(harness, "pause").status_code == 204
    harness.join(HOME)
    then_the_state_becomes(harness, "paused")
    assert when_it_is_controlled(harness, "stop").status_code == 204
    then_the_state_becomes(harness, "stopped")


def test_a_wait_times_out(harness: Harness, directory: Path) -> None:
    when_it_runs(
        harness,
        given_a_scenario(
            directory, [{"wait": "connect", "coach": "home", "timeout": 0.05}]
        ),
    )
    then_it_failed_with(harness, "étape 1 : délai dépassé")


def test_a_delay_lets_time_pass(harness: Harness, directory: Path) -> None:
    when_it_runs(
        harness, given_a_scenario(directory, [{"wait": "delay", "seconds": 0.01}])
    )
    then_the_state_becomes(harness, "done")


def test_an_unexpected_command_fails_and_is_judged_like_automaton(
    harness: Harness, directory: Path
) -> None:
    when_it_runs(
        harness,
        given_a_scenario(
            directory,
            [JOIN_HOME, {"wait": "command", "coach": "home", "type": "end_set_up"}],
        ),
    )
    home = harness.join(HOME)
    home.command(KICK)
    then_it_is_refused(home, 409, "n'attend aucune entrée")
    then_it_failed_with(
        harness, "commande inattendue : choose_kick_off au lieu de end_set_up"
    )


def test_a_missing_bound_field_fails(harness: Harness, directory: Path) -> None:
    when_it_runs(
        harness,
        given_a_scenario(
            directory,
            [
                JOIN_HOME,
                REQUEST,
                {"wait": "command", "coach": "home", "bind": {"square": "s"}},
            ],
        ),
    )
    home = harness.join(HOME)
    then_it_receives(home, type="request")
    home.command(KICK)
    then_it_failed_with(harness, "la commande n'a pas de champ square")


def test_an_unknown_variable_fails(harness: Harness, directory: Path) -> None:
    when_it_runs(
        harness, given_a_scenario(directory, [{"do": "phase", "label": "$nulle_part"}])
    )
    then_it_failed_with(harness, "variable inconnue : $nulle_part")


def test_a_bad_step_fails_when_it_is_reached(harness: Harness, directory: Path) -> None:
    when_it_runs(
        harness,
        given_a_scenario(
            directory, [{"set": {"x": "oops"}}, {"do": "cut", "to": "$x"}]
        ),
    )
    then_it_failed_with(harness, "étape 2 : étape illisible")


def test_a_bad_verdict_fails(harness: Harness, directory: Path) -> None:
    when_it_runs(
        harness,
        given_a_scenario(
            directory,
            [
                JOIN_HOME,
                REQUEST,
                {"wait": "command", "coach": "home", "judge": {"kind": "peut-être"}},
            ],
        ),
    )
    home = harness.join(HOME)
    then_it_receives(home, type="request")
    home.command(KICK)
    then_it_failed_with(harness, "jugement illisible")


def test_a_waiting_command_is_judged_like_automaton_at_the_end(
    harness: Harness, directory: Path
) -> None:
    when_it_runs(
        harness,
        given_a_scenario(directory, [JOIN_HOME, {"wait": "delay", "seconds": 0.3}]),
    )
    home = harness.join(HOME)
    home.command(KICK)
    then_it_is_refused(home, 409, "n'attend aucune entrée")
    then_the_state_becomes(harness, "done")


def test_one_scenario_at_a_time(harness: Harness, directory: Path) -> None:
    file = given_a_scenario(directory, [JOIN_HOME])
    when_it_runs(harness, file)
    second = when_it_runs(harness, file, game_id=GAME)
    assert second.status_code == 409 and "déjà en cours" in second.text


def test_controls_need_a_running_scenario(harness: Harness) -> None:
    for command in ("step", "pause", "resume", "stop"):
        response = when_it_is_controlled(harness, command)
        assert (
            response.status_code == 409 and "aucun scénario en cours" in response.text
        )
    assert when_it_is_controlled(harness, "rewind").status_code == 422


# --- La bibliothèque et la page ---------------------------------------------------------------


def test_the_library_lists_readable_and_unreadable_files(
    harness: Harness, directory: Path
) -> None:
    given_a_scenario(directory, [], name="bon.json", group="Nominal", rule="R5")
    (directory / "cassé.json").write_text("{", encoding="utf-8")
    entries = {e["file"]: e for e in harness.client.get("/pilot/scenarios").json()}
    assert entries["bon.json"]["group"] == "Nominal"
    assert entries["cassé.json"]["group"] == "Illisibles"


def test_an_unknown_or_outside_file_is_refused(harness: Harness) -> None:
    for file in ("absent.json", "../pyproject.toml"):
        response = when_it_runs(harness, file)
        assert response.status_code == 422 and "scénario inconnu" in response.text


def test_the_page_shows_the_library_and_the_run(
    harness: Harness, directory: Path
) -> None:
    file = given_a_scenario(
        directory,
        [
            JOIN_HOME,
            REQUEST,
            {"wait": "command", "coach": "home"},
            {"wait": "delay", "seconds": 1},
            {"set": {"a": 1}},
            {"do": "fact", "fact": {"type": "roll_off_won", "side": "home"}},
            {"do": "cut", "to": "home"},
            {"do": "finish", "note": "fin"},
        ],
        group="Nominal",
    )
    page = harness.client.get("/ui/scenarios")
    assert (
        "Nominal" in page.text
        and "Lancer" in page.text
        and "connexion du coach home" in page.text
    )
    when_it_runs(harness, file, step_mode=True)
    with harness.client.websocket_connect(f"/ui/scenarios/ws?file={file}") as watcher:
        assert "en pause" in watcher.receive_text()
    page = harness.client.get(f"/ui/scenarios?file={file}")
    assert "Pas ▸" in page.text and "fin" in page.text


def test_the_empty_library_page(harness: Harness) -> None:
    assert "Aucun scénario" in harness.client.get("/ui/scenarios").text


# --- L'export du fil -----------------------------------------------------------------------------


def test_the_wire_exports_as_a_replayable_scenario(
    harness: Harness, directory: Path
) -> None:
    harness.create_game()
    home = harness.join(HOME)
    harness.do(REQUEST)
    then_it_receives(home, type="request")
    home.command(KICK)
    then_it_is_accepted(home)
    harness.settings(judge="manual")
    harness.do(request_to("home"))
    then_it_receives(home, type="request")
    home.command(KICK)
    harness.judge(
        harness.wait_pending()[0]["number"],
        kind="accept",
        then=[{"do": "phase", "label": "x"}],
    )
    then_it_is_accepted(home)
    exported = harness.client.get(f"/ui/games/{GAME}/scenario.json").json()
    assert exported["game"]["home_coach"] == HOME
    assert [s.get("wait") or s.get("do") for s in exported["steps"]] == [
        "connect",
        "request",
        "command",
        "request",
        "command",
    ]
    assert exported["steps"][-1]["judge"] == {
        "kind": "accept",
        "then": [{"do": "phase", "label": "x"}],
    }
    (directory / "export.json").write_text(json.dumps(exported), encoding="utf-8")
    assert load(directory / "export.json").name.startswith("Fil du match")


# --- Le format ----------------------------------------------------------------------------------


def test_variables_are_substituted_whole_or_inside_text() -> None:
    assert substitute({"a": "$x", "b": ["v=$x"], "c": 3}, {"x": 7}) == {
        "a": 7,
        "b": ["v=7"],
        "c": 3,
    }


def test_derive_takes_a_literal_or_a_table() -> None:
    assert derive("home", {}) == "home"
    then_it_fails_with(
        attempt(lambda: derive({"from": "$k", "map": {}}, {"k": "kick"})),
        ScenarioError,
        "'kick' absent de la table",
    )


def test_an_unknown_step_is_refused() -> None:
    then_it_fails_with(
        attempt(lambda: parse_step({"hop": 1})), ScenarioError, "étape inconnue"
    )


def test_loading_checks_the_steps_without_variables(directory: Path) -> None:
    given_a_scenario(directory, [{"do": "voler"}], name="mauvais.json")
    then_it_fails_with(
        attempt(lambda: load(directory / "mauvais.json")),
        InvalidInput,
        "mauvais.json, étape 1",
    )
    (directory / "pas-json.json").write_text("[", encoding="utf-8")
    then_it_fails_with(
        attempt(lambda: load(directory / "pas-json.json")),
        InvalidInput,
        "scénario illisible",
    )


def test_ids_are_the_scenario_ones() -> None:
    assert IDS["visitor_coach"] == VISITOR
