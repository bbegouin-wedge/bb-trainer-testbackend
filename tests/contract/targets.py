"""Les deux serveurs que la suite compare : la doublure, et le vrai automaton.

Chacun est lancé dans son propre processus, sur un port libre, et parle sur
le réseau : la suite ne voit que ce que voit un client.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.live import free_port


@dataclass
class Target:
    name: str
    port: int
    console_port: int | None = None
    created: list[str] = field(default_factory=list)

    @property
    def ws(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    def post(self, port: int, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}

    def create_game(self, ids: dict[str, str]) -> str:
        game_id: str = self.post(self.port, "/games", ids)["game_id"]
        self.created.append(game_id)
        return game_id

    def offer_kick_off(self, game_id: str, coach_side: str) -> None:
        """Automaton ouvre lui-même la demande ; la doublure, par son pilotage."""
        if self.console_port is None:
            return
        action = {
            "do": "request",
            "to": coach_side,
            "key": "kick_off_choice",
            "options": {"accepts": ["choose_kick_off"], "choices": ["kick", "receive"]},
        }
        self.post(self.console_port, f"/pilot/games/{game_id}/actions", action)


def _wait_port(port: int, process: subprocess.Popen[bytes]) -> None:
    import socket

    end = time.monotonic() + 30
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError(f"le serveur s'est arrêté (code {process.returncode})")
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"le port {port} n'a jamais ouvert")


@contextmanager
def _process(command: list[str], cwd: Path, port: int) -> Iterator[None]:
    process = subprocess.Popen(
        command, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        _wait_port(port, process)
        yield
    finally:
        process.terminate()
        process.wait(10)


@contextmanager
def doublure() -> Iterator[Target]:
    port, console = free_port(), free_port()
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-m",
        "testbackend",
        "--port",
        str(port),
        "--console-port",
        str(console),
    ]
    with _process(command, root, port):
        yield Target("doublure", port, console)


@contextmanager
def automaton() -> Iterator[Target]:
    directory = Path(os.environ["AUTOMATON_DIR"])
    port = free_port()
    command = [
        "uv",
        "run",
        "--quiet",
        "uvicorn",
        "bloodbowl.api.main:app",
        "--port",
        str(port),
    ]
    target = Target("automaton", port)
    with _process(command, directory, port):
        try:
            yield target
        finally:
            for game_id in target.created:
                (
                    directory / "bloodbowl" / "data" / "journals" / f"{game_id}.jsonl"
                ).unlink(missing_ok=True)
