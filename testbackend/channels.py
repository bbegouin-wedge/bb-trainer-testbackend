"""Le canal du coach : `/games/{game_id}/coaches/{coach_id}/ws`, comme automaton.

Trois tâches par socket :
- la lecture date chaque message à son arrivée (R2), puis le range ;
- le traitement juge les messages un par un, dans l'ordre de lecture ;
- l'envoi est le seul écrivain de la socket : tout ce qui descend passe par
  sa file, dans l'ordre, retards compris.
La socket se ferme quand le client part ou quand une coupure est demandée.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from testbackend.backend import Backend, Channel, Close
from testbackend.ids import Side
from testbackend.protocol import Refusal, encode, refused_frame

# La clé du scope où la sonde du serveur range le transport TCP de la socket.
TRANSPORT_KEY = "testbackend.transport"


def create_channel_router(backend: Backend) -> APIRouter:
    router = APIRouter()

    @router.websocket("/games/{game_id}/coaches/{coach_id}/ws")
    async def coach_channel(websocket: WebSocket, game_id: str, coach_id: str) -> None:
        await websocket.accept()
        admission = backend.admit(game_id, coach_id)
        if isinstance(admission, Refusal):
            frame = refused_frame(admission, backend.settings.variants)
            await websocket.send_text(encode(frame))
            await websocket.close(code=4000 + admission.status)
            return
        side = admission.side
        channel = Channel()
        backend.open_channel(game_id, side, channel, admission.fail_arrival)
        tasks = [
            asyncio.create_task(_send_all(websocket, channel)),
            asyncio.create_task(
                _receive_all(websocket, backend, game_id, side, channel)
            ),
        ]
        processor = asyncio.create_task(_process_all(backend, game_id, side, channel))
        code: int | None = None
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            code = next(iter(done)).result()
        finally:
            for task in [*tasks, processor]:
                task.cancel()
            backend.close_channel(game_id, side, channel, code)

    return router


async def _receive_all(
    websocket: WebSocket, backend: Backend, game_id: str, side: Side, channel: Channel
) -> int:
    try:
        while True:
            raw = await websocket.receive_text()
            backend.received(game_id, side, raw)
            channel.inbox.put_nowait(raw)
    except WebSocketDisconnect as disconnect:
        return disconnect.code


async def _process_all(
    backend: Backend, game_id: str, side: Side, channel: Channel
) -> None:
    while True:
        await backend.process(game_id, side, await channel.inbox.get())


async def _send_all(websocket: WebSocket, channel: Channel) -> int:
    while True:
        item = await channel.outbox.get()
        try:
            if isinstance(item, Close):
                return await _close(websocket, item)
            text, delay = item
            if delay:
                await asyncio.sleep(delay)
            await websocket.send_text(text)
        finally:
            channel.outbox.task_done()


async def _close(websocket: WebSocket, close: Close) -> int:
    """Ferme la socket. Une coupure brutale abandonne le transport TCP sans
    trame de fermeture : le client voit 1006, comme sur une panne réseau."""
    if close.mode == "clean":
        await websocket.close(code=1000)
        return 1000
    transport: Any = websocket.scope.get(TRANSPORT_KEY)
    if transport is not None:
        transport.abort()
    else:  # sans serveur réel (client de test) : le code seul
        await websocket.close(code=1006)
    return 1006
