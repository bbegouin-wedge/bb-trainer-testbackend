"""Les scénarios par HTTP : la bibliothèque, la lecture, la page, l'export du fil.

Les fichiers de `scenarios/` sont la seule source : la page les montre et les
joue, elle ne les modifie pas. Un nouveau scénario se fait en exportant le fil
d'un match joué à la main (« En scénario »), puis en retouchant le fichier.
"""

import json
from typing import Any

from fastapi import APIRouter, Request, WebSocket, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from testbackend.backend import Backend
from testbackend.console import push_on_change, templates
from testbackend.errors import InvalidInput
from testbackend.scenario.model import Scenario, load
from testbackend.scenario.runner import Runner


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    game_id: str | None = None
    step_mode: bool = False


def create_scenario_router(backend: Backend, runner: Runner) -> APIRouter:
    router = APIRouter()

    def library() -> list[dict[str, Any]]:
        entries = []
        for path in sorted(runner.directory.glob("*.json")):
            try:
                scenario = load(path)
            except InvalidInput as err:
                entries.append(
                    {
                        "file": path.name,
                        "name": path.name,
                        "group": "Illisibles",
                        "description": str(err),
                    }
                )
                continue
            entries.append(
                {
                    "file": path.name,
                    "name": scenario.name,
                    "group": scenario.group,
                    "description": scenario.description,
                    "rule": scenario.rule,
                }
            )
        return entries

    def read(file: str) -> Scenario:
        path = runner.directory / file
        if path.parent != runner.directory or not path.is_file():
            raise InvalidInput(f"scénario inconnu : {file}")
        return load(path)

    @router.get("/pilot/scenarios")
    def scenarios() -> list[dict[str, Any]]:
        return library()

    @router.get("/pilot/scenarios/state")
    def state() -> dict[str, Any]:
        s = runner.state
        return {
            "file": s.file,
            "game_id": s.game_id,
            "status": s.status,
            "index": s.index,
            "variables": s.variables,
            "error": s.error,
        }

    @router.post("/pilot/scenarios/run", status_code=status.HTTP_201_CREATED)
    async def run(body: Run) -> dict[str, str]:
        game_id = await runner.start(
            read(body.file), body.file, body.game_id, body.step_mode
        )
        return {"game_id": game_id}

    @router.post("/pilot/scenarios/{command}", status_code=status.HTTP_204_NO_CONTENT)
    async def control(command: str) -> None:
        match command:
            case "step":
                runner.step()
            case "pause":
                runner.pause()
            case "resume":
                runner.resume()
            case "stop":
                await runner.stop()
            case _:
                raise InvalidInput(f"commande de lecture inconnue : {command}")

    @router.get("/ui/games/{game_id}/scenario.json")
    def export(game_id: str) -> dict[str, Any]:
        """Le fil du match en scénario : ses gestes, rejouables tels quels."""
        game = backend.game(game_id)
        return {
            "name": f"Fil du match {game.game_id}",
            "description": "exporté depuis la console",
            "game": {
                "game_id": game.game_id,
                **{
                    f"{side}_{k}": getattr(c, f"{k}_id")
                    for side, c in game.coaches.items()
                    for k in ("coach", "team")
                },
            },
            "settings": {"relay_facts": backend.settings.relay_facts},
            "steps": game.script,
        }

    def page_context(file: str | None) -> dict[str, Any]:
        entries = library()
        selected = file or (
            runner.state.file or (entries[0]["file"] if entries else None)
        )
        scenario = read(selected) if selected else None
        game = backend.games.get(runner.state.game_id)
        return {
            "page": "scenarios",
            "backend": backend,
            "game": game,
            "library": entries,
            "file": selected,
            "scenario": scenario,
            "steps": [describe(step) for step in scenario.steps] if scenario else [],
            "run": runner.state,
            "games": list(backend.games.values()),
        }

    @router.get("/ui/scenarios", response_class=HTMLResponse)
    def page(request: Request, file: str | None = None) -> HTMLResponse:
        return templates.TemplateResponse(request, "scenarios.html", page_context(file))

    @router.websocket("/ui/scenarios/ws")
    async def observe(websocket: WebSocket, file: str | None = None) -> None:
        def mark() -> tuple[Any, ...]:
            run = runner.state
            game = backend.games.get(run.game_id)
            return (run.status, run.index, run.game_id, game.version if game else -1)

        await push_on_change(
            backend,
            websocket,
            mark=mark,
            render=lambda: templates.get_template("_scenario_live.html").render(
                page_context(file)
            ),
        )

    return router


_DO_KIND = {
    "request": "req",
    "reopen": "req",
    "close": "req",
    "fact": "fact",
    "finish": "end",
    "phase": "end",
}


def describe(raw: dict[str, Any]) -> dict[str, str]:
    """Une étape pour l'affichage : sa sorte, son étiquette, son libellé."""
    shown = {k: v for k, v in raw.items() if k != "note"}
    step = {
        "detail": json.dumps(shown, ensure_ascii=False),
        "note": raw.get("note", ""),
    }
    if "do" in raw:
        label = {
            "request": f"demande {raw.get('key')} → {raw.get('to')}",
            "fact": f"fait {raw.get('fact', {}).get('type')}",
            "phase": f"étape « {raw.get('label')} »",
        }.get(raw["do"], raw["do"])
        return step | {
            "kind": _DO_KIND.get(raw["do"], "chaos"),
            "tag": raw["do"],
            "label": label,
        }
    match raw.get("wait"):
        case "connect":
            label = f"connexion du coach {raw.get('coach')}"
        case "command":
            label = f"{raw.get('type') or 'une commande'} du coach {raw.get('coach')}"
        case "delay":
            label = f"{raw.get('seconds')} s"
        case _:
            return step | {
                "kind": "end",
                "tag": "variables",
                "label": ", ".join(raw.get("set", {})),
            }
    return step | {"kind": "wait", "tag": "attendre", "label": label}
