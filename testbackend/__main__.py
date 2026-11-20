"""Point d'entrée : `python -m testbackend` (make serve, make play).

Sert les canaux (port de bbTrainer) et la console, dans une même boucle.
Dès que tout écoute, écrit sur la sortie une ligne JSON « ready » : le match
du scénario et ses deux places, pour qu'un banc de test (la CI de bbTrainer)
sache où brancher ses clients.

Avec --scenario, joue le scénario puis s'arrête : code de sortie 0 s'il va au
bout, 1 sinon (--keep garde le serveur ouvert après).
"""

import argparse
import asyncio
import json
import signal
import sys
from collections.abc import Coroutine, Sequence
from pathlib import Path
from typing import Any

from testbackend.app import create_app, created
from testbackend.backend import Backend
from testbackend.scenario.model import load
from testbackend.scenario.runner import DEFAULT_DIRECTORY, Runner
from testbackend.server import UvicornListener


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="testbackend", description=__doc__.splitlines()[0]
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="canaux (bbTrainer)")
    parser.add_argument("--console-port", type=int, default=8001)
    parser.add_argument("--judge", choices=["auto", "manual"], default="auto")
    parser.add_argument("--relay-facts", action="store_true")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--scenario", type=Path, help="joue ce scénario, puis s'arrête")
    parser.add_argument("--step", action="store_true", help="scénario en pas à pas")
    parser.add_argument(
        "--keep", action="store_true", help="reste ouvert après le scénario"
    )
    return parser.parse_args(argv)


async def serve(args: argparse.Namespace, stop: asyncio.Event) -> int:
    backend = Backend()
    backend.channels_url = f"ws://{args.host}:{args.port}"
    backend.update_settings({"judge": args.judge, "relay_facts": args.relay_facts})
    runner = Runner(backend, args.scenarios)
    channels = UvicornListener(
        create_app(backend, runner, console=False), args.host, args.port
    )
    console = UvicornListener(
        create_app(backend, runner, channels=False), args.host, args.console_port
    )
    backend.listener = channels
    await channels.start()
    await console.start()
    code = 0
    try:
        ready = {
            "event": "ready",
            "channels": backend.channels_url,
            "console": f"http://{args.host}:{args.console_port}",
        }
        if args.scenario:
            game_id = await runner.start(
                load(args.scenario), args.scenario.name, step_mode=args.step
            )
            ready |= created(backend.game(game_id))
        print(json.dumps(ready), flush=True)
        if args.scenario:
            state = await _until(runner.wait(), stop)
            code = 0 if state is not None and state.status == "done" else 1
            print(
                json.dumps(
                    {
                        "event": "end",
                        "status": runner.state.status,
                        "error": runner.state.error,
                    }
                ),
                flush=True,
            )
            if not args.keep:
                return code
        await stop.wait()
        return code
    finally:
        await backend.drain()
        await channels.stop()
        await console.stop()


async def _until[T](work: Coroutine[Any, Any, T], stop: asyncio.Event) -> T | None:
    """Le résultat de `work`, ou None si l'arrêt est demandé avant."""
    task = asyncio.create_task(work)
    stopper = asyncio.create_task(stop.wait())
    await asyncio.wait({task, stopper}, return_when=asyncio.FIRST_COMPLETED)
    stopper.cancel()
    if not task.done():
        task.cancel()
        return None
    result: T = task.result()
    return result


async def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    return await serve(args, stop)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
