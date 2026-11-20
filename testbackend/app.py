"""Les applications HTTP : les canaux d'un côté, la console de l'autre.

- Côté canaux (le port que bbTrainer connaît) : le websocket du coach, et les
  routes d'automaton, `POST /games` et `GET /games/{id}/journal`.
- Côté console : l'API de pilotage (`/pilot/…`) et les pages.

Les deux côtés partagent le même Backend. `make serve` les sert sur deux
ports, pour que la panne « serveur qui tombe » coupe les canaux sans couper
la console ; les tests les montent ensemble, dans une seule application.
"""

from typing import Any

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from testbackend.actions import Action, Verdict
from testbackend.backend import Backend, Settings
from testbackend.channels import create_channel_router
from testbackend.console import create_console_router, static_files
from testbackend.errors import PilotError
from testbackend.game import Game
from testbackend.scenario.routes import create_scenario_router
from testbackend.scenario.runner import Runner


class CreateGame(BaseModel):
    """Le corps de `POST /games` : celui d'automaton, identifiants facultatifs."""

    model_config = ConfigDict(extra="forbid")

    game_id: str | None = None
    home_coach: str | None = None
    home_team: str | None = None
    visitor_coach: str | None = None
    visitor_team: str | None = None


def create_app(
    backend: Backend,
    runner: Runner | None = None,
    channels: bool = True,
    console: bool = True,
) -> FastAPI:
    app = FastAPI(title="bb-testbackend")
    if channels:
        app.include_router(create_channel_router(backend))
        app.include_router(_automaton_router(backend))
    if console:
        app.include_router(_pilot_router(backend))
        app.include_router(create_scenario_router(backend, runner or Runner(backend)))
        app.include_router(create_console_router(backend))
        app.mount("/ui/static", static_files(), name="static")

    async def pilot_error(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, PilotError)
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    app.add_exception_handler(PilotError, pilot_error)
    return app


def _automaton_router(backend: Backend) -> APIRouter:
    router = APIRouter(prefix="/games")

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_game(body: CreateGame) -> dict[str, str]:
        return {"game_id": backend.create_game(**body.model_dump()).game_id}

    @router.get("/{game_id}/journal")
    def journal(game_id: str) -> dict[str, Any]:
        return backend.snapshot(game_id)

    return router


def _pilot_router(backend: Backend) -> APIRouter:
    router = APIRouter(prefix="/pilot")

    @router.get("/catalog")
    def catalog() -> dict[str, Any]:
        c = backend.catalog
        return {
            "commands": {k: v.fields for k, v in c.commands.items()},
            "requests": {k: v.options for k, v in c.requests.items()},
            "facts": {k: c.fact_example(k) for k in c.facts},
        }

    @router.get("/games")
    def games() -> list[dict[str, Any]]:
        return [created(g) for g in backend.games.values()]

    @router.post("/games", status_code=status.HTTP_201_CREATED)
    def create_game(body: CreateGame) -> dict[str, Any]:
        return created(backend.create_game(**body.model_dump()))

    @router.get("/games/{game_id}")
    def game(game_id: str) -> dict[str, Any]:
        return backend.snapshot(game_id)

    @router.post("/games/{game_id}/actions", status_code=status.HTTP_204_NO_CONTENT)
    async def act(game_id: str, action: Action) -> None:
        await backend.apply(game_id, action)

    @router.post(
        "/games/{game_id}/pending/{number}/verdict",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def judge(game_id: str, number: int, verdict: Verdict) -> None:
        backend.judge(game_id, number, verdict)

    @router.post(
        "/games/{game_id}/pending/{number}/stage",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def stage(game_id: str, number: int, action: Action) -> None:
        backend.stage(game_id, number, action)

    @router.get("/settings")
    def settings() -> Settings:
        return backend.settings

    @router.patch("/settings")
    def update_settings(changes: dict[str, Any]) -> Settings:
        return backend.update_settings(changes)

    return router


def created(game: Game) -> dict[str, Any]:
    """Ce qu'il faut à un client pour rejoindre : le match et ses deux places."""
    return {
        "game_id": game.game_id,
        "home_coach": game.coaches["home"].coach_id,
        "home_team": game.coaches["home"].team_id,
        "visitor_coach": game.coaches["visitor"].coach_id,
        "visitor_team": game.coaches["visitor"].team_id,
    }
