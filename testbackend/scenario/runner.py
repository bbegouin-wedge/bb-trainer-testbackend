"""Le lecteur de scénarios : il joue les étapes, une à une, à la place de
l'opérateur.

Pendant la lecture, le jugement passe en mode « scénario » : chaque commande
lisible attend qu'une étape `wait: command` la juge. Les réglages du
scénario s'appliquent le temps de la lecture ; ceux d'avant reviennent à la
fin, et une commande encore en attente est alors jugée comme automaton, pour
qu'aucun client ne reste suspendu.

Un seul scénario se lit à la fois. Il réussit s'il va au bout ; il échoue au
premier délai dépassé, à la première commande inattendue ou étape illisible.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from testbackend.actions import Verdict
from testbackend.backend import Backend, Settings
from testbackend.errors import Conflict, PilotError
from testbackend.scenario.model import (
    Scenario,
    ScenarioError,
    SetVars,
    WaitCommand,
    WaitConnect,
    WaitDelay,
    derive,
    parse_step,
    parse_verdict,
    substitute,
)

DEFAULT_DIRECTORY = Path(__file__).resolve().parents[2] / "scenarios"

type Status = Literal["idle", "running", "paused", "done", "failed", "stopped"]


@dataclass
class RunState:
    scenario: Scenario | None = None
    file: str = ""
    game_id: str = ""
    status: Status = "idle"
    index: int = 0  # l'étape en cours, ou la suivante en pas à pas
    variables: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def active(self) -> bool:
        return self.status in ("running", "paused")


class Runner:
    def __init__(self, backend: Backend, directory: Path = DEFAULT_DIRECTORY) -> None:
        self.backend = backend
        self.directory = directory
        self.state = RunState()
        self._task: asyncio.Task[None] | None = None
        self._go = asyncio.Event()
        self._step_mode = False

    async def start(
        self,
        scenario: Scenario,
        file: str = "",
        game_id: str | None = None,
        step_mode: bool = False,
    ) -> str:
        if self.state.active:
            raise Conflict(f"un scénario est déjà en cours : {self.state.file}")
        game = (
            self.backend.game(game_id)
            if game_id
            else self.backend.create_game(**scenario.game.model_dump())
        )
        self.state = RunState(
            scenario, file, game.game_id, "paused" if step_mode else "running"
        )
        self._step_mode = step_mode
        self._go.clear()
        previous = self.backend.settings
        self.backend.update_settings({**scenario.settings, "judge": "scenario"})
        self._task = asyncio.create_task(self._run(scenario, previous))
        return game.game_id

    def step(self) -> None:
        """En pas à pas : joue l'étape suivante."""
        self._require_active()
        self._go.set()

    def pause(self) -> None:
        self._require_active()
        self._step_mode = True

    def resume(self) -> None:
        self._require_active()
        self._step_mode = False
        self._go.set()

    async def stop(self) -> None:
        self._require_active()
        assert self._task is not None
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)

    async def wait(self) -> RunState:
        """Attend la fin du scénario en cours."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)
        return self.state

    # --- Interne -------------------------------------------------------------------

    async def _run(self, scenario: Scenario, previous: Settings) -> None:
        state = self.state
        try:
            for index, raw in enumerate(scenario.steps):
                state.index = index
                if self._step_mode:
                    self._set_status("paused")
                    await self._go.wait()
                    self._go.clear()
                self._set_status("running")
                await self._execute(raw)
            state.index = len(scenario.steps)
            state.status = "done"
        except TimeoutError:
            self._fail(f"étape {state.index + 1} : délai dépassé")
        except (ScenarioError, PilotError, ValidationError) as err:
            self._fail(f"étape {state.index + 1} : {err}")
        except asyncio.CancelledError:
            state.status = "stopped"
        finally:
            self._restore(previous)

    async def _execute(self, raw: dict[str, Any]) -> None:
        state = self.state
        game = self.backend.game(state.game_id)
        # `set` et `judge` se lisent plus tard : ils citent des variables que
        # l'étape elle-même lie.
        deferred = {k: raw[k] for k in ("set", "judge") if k in raw}
        rest = {k: v for k, v in raw.items() if k not in deferred}
        step = parse_step(substitute(rest, state.variables) | deferred)
        match step:
            case WaitConnect(coach=coach, timeout=timeout):
                await self.backend.wait_for(
                    lambda: game.coaches[coach].connected or None, timeout
                )
            case WaitDelay(seconds=seconds):
                await asyncio.sleep(seconds)
            case WaitCommand():
                await self._wait_command(step)
            case SetVars(set=assignments):
                for name, spec in assignments.items():
                    state.variables[name] = derive(spec, state.variables)
            case action:
                await self.backend.apply(state.game_id, action, record=False)

    async def _wait_command(self, step: WaitCommand) -> None:
        state = self.state
        game = self.backend.game(state.game_id)
        pending = await self.backend.wait_for(
            lambda: game.first_pending(step.coach), step.timeout
        )
        command = pending.uplink.command
        if step.type is not None and pending.uplink.type != step.type:
            self.backend.judge(state.game_id, pending.number, Verdict())
            raise ScenarioError(
                f"commande inattendue : {pending.uplink.type} au lieu de {step.type}"
            )
        for field_name, variable in step.bind.items():
            if field_name not in command:
                raise ScenarioError(f"la commande n'a pas de champ {field_name}")
            state.variables[variable] = command[field_name]
        for name, spec in step.set.items():
            state.variables[name] = derive(spec, state.variables)
        verdict = parse_verdict(substitute(step.judge, state.variables))
        await self.backend.judge(state.game_id, pending.number, verdict)

    def _restore(self, previous: Settings) -> None:
        self.backend.settings = previous
        if previous.judge == "auto":
            game = self.backend.game(self.state.game_id)
            for pending in list(game.pending):
                self.backend.judge(game.game_id, pending.number, Verdict())
        self._touch()

    def _set_status(self, status: Status) -> None:
        self.state.status = status
        self._touch()

    def _fail(self, message: str) -> None:
        self.state.status = "failed"
        self.state.error = message

    def _touch(self) -> None:
        self.backend.touch(self.state.game_id)

    def _require_active(self) -> None:
        if not self.state.active:
            raise Conflict("aucun scénario en cours")
