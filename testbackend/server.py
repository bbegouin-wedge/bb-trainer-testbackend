"""Les deux serveurs dans une même boucle : les canaux et la console.

Les canaux écoutent sur le port que bbTrainer connaît ; leur écoute s'arrête
et se relance à la demande (panne « serveur qui tombe »), sans toucher à la
console ni aux matchs. Les signaux (Ctrl-C) sont traités ici, une fois, et
pas par chaque serveur uvicorn.
"""

import asyncio
import socket
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI

from testbackend.channels import TRANSPORT_KEY

type Scope = dict[str, Any]


class TransportProbe:
    """Middleware ASGI le plus externe : range dans le scope le transport TCP de
    la socket, que seule la coupure brutale utilise. Uvicorn passe à l'application
    la méthode `asgi_send` de son protocole, qui porte ce transport."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] == "websocket":
            protocol = getattr(send, "__self__", None)
            scope[TRANSPORT_KEY] = getattr(protocol, "transport", None)
        await self.app(scope, receive, send)


class _Server(uvicorn.Server):
    @contextmanager
    def capture_signals(self) -> Generator[None]:
        yield  # les signaux sont traités par run_servers


class UvicornListener:
    """Un serveur uvicorn qu'on arrête et relance dans la boucle courante."""

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        self._config = uvicorn.Config(
            TransportProbe(app),
            host=host,
            port=port,
            log_level="warning",
            lifespan="off",
        )
        self._server: _Server | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def listening(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Écoute ; lève OSError si le port est pris. Le port est réservé ici,
        avant uvicorn, qui sinon quitterait le processus entier (sys.exit)."""
        if self.listening:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self._config.host, self._config.port))
        except OSError:
            sock.close()
            raise
        self._server = server = _Server(self._config)
        self._task = asyncio.create_task(server.serve(sockets=[sock]))
        while not server.started:
            await asyncio.sleep(0.01)

    async def stop(self) -> None:
        if self._server is None or self._task is None or not self.listening:
            return
        self._server.should_exit = True
        await self._task
