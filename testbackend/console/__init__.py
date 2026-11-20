"""La console : des pages en lecture, et rien d'autre.

Elle ne change jamais l'état elle-même : ses boutons et formulaires appellent
l'API de pilotage (`/pilot/…`), comme n'importe quel client. Elle ne fait que
dessiner, et redessiner à chaque changement, poussé par un websocket
d'observateur. Chaque région de la page est une macro de `_regions.html` :
la page la dessine une fois, le websocket la redessine (swap hors-bande
HTMX, par son `id`).
"""

import asyncio
import json
from collections.abc import Callable, Hashable
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from testbackend.backend import Backend
from testbackend.ids import SIDE_LABEL

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["clock"] = lambda at: datetime.fromtimestamp(at).strftime(
    "%H:%M:%S"
)
templates.env.filters["short"] = lambda value: f"{value[:10]}…{value[-4:]}"
templates.env.filters["pretty"] = lambda value: json.dumps(value, ensure_ascii=False)
templates.env.globals["SIDE_LABEL"] = SIDE_LABEL


def create_console_router(backend: Backend) -> APIRouter:
    router = APIRouter(include_in_schema=False)

    def context(game_id: str | None, **extra: Any) -> dict[str, Any]:
        game = backend.game(game_id) if game_id else None
        return {
            "backend": backend,
            "game": game,
            "settings": backend.settings,
            "catalog": backend.catalog,
            "conformity": backend.conformity(game_id) if game_id else [],
            "channels_url": backend.channels_url,
            "catalog_json": {
                "requests": {k: v.options for k, v in backend.catalog.requests.items()},
                "facts": {
                    k: backend.catalog.fact_example(k) for k in backend.catalog.facts
                },
            },
            **extra,
        }

    @router.get("/")
    def index(request: Request) -> Response:
        if backend.games:
            latest = list(backend.games)[-1]
            return RedirectResponse(f"/ui/games/{latest}")
        return templates.TemplateResponse(request, "console.html", context(None))

    @router.get("/ui/games/{game_id}", response_class=HTMLResponse)
    def console(request: Request, game_id: str) -> HTMLResponse:
        return templates.TemplateResponse(request, "console.html", context(game_id))

    @router.websocket("/ui/games/{game_id}/ws")
    async def observe(websocket: WebSocket, game_id: str) -> None:
        game = backend.game(game_id)
        await push_on_change(
            backend,
            websocket,
            mark=lambda: game.version,
            render=lambda: templates.get_template("_live.html").render(
                context(game_id)
            ),
        )

    return router


def static_files() -> StaticFiles:
    """Les feuilles et scripts de la console, servis sous /ui/static."""
    return StaticFiles(directory=HERE / "static")


async def push_on_change(
    backend: Backend,
    websocket: WebSocket,
    mark: Callable[[], Hashable],
    render: Callable[[], str],
) -> None:
    """Un websocket d'observateur : pousse `render()` à chaque changement de
    `mark()`, jusqu'à ce que la page parte."""
    await websocket.accept()
    listener = asyncio.create_task(_until_closed(websocket))
    seen: Hashable = object()
    try:
        while True:
            changed = asyncio.create_task(backend.wait_for(_changed_since(mark, seen)))
            await asyncio.wait({changed, listener}, return_when=asyncio.FIRST_COMPLETED)
            if listener.done():
                changed.cancel()
                return
            (seen,) = changed.result()
            await websocket.send_text(render())
    finally:
        listener.cancel()


def _changed_since(
    mark: Callable[[], Hashable], seen: Hashable
) -> Callable[[], tuple[Hashable] | None]:
    """Le prédicat d'attente : la nouvelle marque, dès qu'elle diffère."""

    def predicate() -> tuple[Hashable] | None:
        current = mark()
        return (current,) if current != seen else None

    return predicate


async def _until_closed(websocket: WebSocket) -> None:
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
