"""Le banc réel : la doublure sur de vrais ports, des clients de référence en face."""

import asyncio
import socket
from pathlib import Path

from testbackend.__main__ import parse_args, serve
from tests.harness import GAME, HOME, VISITOR
from tests.reference_client import ReferenceClient

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def channel_url(port: int, coach_id: str) -> str:
    return f"ws://127.0.0.1:{port}/games/{GAME}/coaches/{coach_id}/ws"


def play(
    scenario: Path, *extra: str, clients: bool = True
) -> tuple[int, list[ReferenceClient]]:
    """Joue le scénario sur de vrais ports ; rend le code de sortie et les clients."""
    port, console = free_port(), free_port()
    coaches = (
        [ReferenceClient(channel_url(port, c), deadline=40) for c in (HOME, VISITOR)]
        if clients
        else []
    )
    for client in coaches:
        client.start()
    args = parse_args(
        [
            "--port",
            str(port),
            "--console-port",
            str(console),
            "--scenario",
            str(scenario),
            *extra,
        ]
    )
    code = asyncio.run(serve(args, asyncio.Event()))
    for client in coaches:
        client.join(5)
    return code, coaches
