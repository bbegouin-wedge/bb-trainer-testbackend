"""Carte 9 — La ligne de commande : jouer un scénario et rendre un code de sortie."""

import asyncio
import json
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from testbackend.__main__ import main, parse_args, serve
from testbackend.app import create_app
from testbackend.backend import Backend
from testbackend.server import UvicornListener
from tests.harness import HOME, VISITOR
from tests.live import SCENARIOS, channel_url, free_port
from tests.reference_client import ReferenceClient


def args_for(*extra: str) -> list[str]:
    return ["--port", str(free_port()), "--console-port", str(free_port()), *extra]


async def stopped_after(
    work: Coroutine[Any, Any, int], stop: asyncio.Event, delay: float
) -> int:
    async def later() -> None:
        await asyncio.sleep(delay)
        stop.set()

    asyncio.get_running_loop().create_task(later())
    return await work


def test_main_plays_a_scenario_and_says_where_to_connect(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = args_for("--scenario", str(SCENARIOS / "coach-refuse.json"))
    port = argv[1]
    coaches = [
        ReferenceClient(channel_url(int(port), c), deadline=20).start()
        for c in (HOME, VISITOR)
    ]
    assert asyncio.run(main(argv)) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["event"] == "ready" and lines[0]["home_coach"] == HOME
    assert lines[0]["channels"] == f"ws://127.0.0.1:{port}"
    assert lines[1] == {"event": "end", "status": "done", "error": ""}
    for coach in coaches:
        coach.join(5)


def test_a_failing_scenario_exits_with_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scenario = tmp_path / "s.json"
    scenario.write_text(
        json.dumps(
            {
                "name": "s",
                "steps": [{"wait": "connect", "coach": "home", "timeout": 0.05}],
            }
        )
    )
    assert (
        asyncio.run(
            serve(parse_args(args_for("--scenario", str(scenario))), asyncio.Event())
        )
        == 1
    )
    assert "délai dépassé" in capsys.readouterr().out.encode().decode("unicode_escape")


def test_a_stop_during_the_scenario_exits_with_1(tmp_path: Path) -> None:
    scenario = tmp_path / "s.json"
    scenario.write_text(
        json.dumps({"name": "s", "steps": [{"wait": "delay", "seconds": 5}]})
    )
    stop = asyncio.Event()
    code = asyncio.run(
        stopped_after(
            serve(parse_args(args_for("--scenario", str(scenario))), stop), stop, 0.2
        )
    )
    assert code == 1


def test_keep_stays_open_after_the_scenario(tmp_path: Path) -> None:
    scenario = tmp_path / "s.json"
    scenario.write_text(json.dumps({"name": "s", "steps": []}))
    stop = asyncio.Event()
    args = parse_args(
        args_for(
            "--scenario", str(scenario), "--keep", "--judge", "manual", "--relay-facts"
        )
    )
    assert asyncio.run(stopped_after(serve(args, stop), stop, 0.2)) == 0


def test_without_scenario_it_serves_until_stopped() -> None:
    stop = asyncio.Event()
    assert (
        asyncio.run(stopped_after(serve(parse_args(args_for()), stop), stop, 0.1)) == 0
    )


def test_the_listener_starts_and_stops_once() -> None:
    async def scenario() -> None:
        listener = UvicornListener(
            create_app(Backend(), console=False), "127.0.0.1", free_port()
        )
        await listener.stop()
        await listener.start()
        await listener.start()
        assert listener.listening
        await listener.stop()
        assert not listener.listening

    asyncio.run(scenario())


def test_a_busy_port_fails_to_start() -> None:
    async def scenario() -> None:
        port = free_port()
        first = UvicornListener(create_app(Backend(), console=False), "127.0.0.1", port)
        await first.start()
        try:
            second = UvicornListener(
                create_app(Backend(), console=False), "127.0.0.1", port
            )
            with pytest.raises(OSError):
                await second.start()
        finally:
            await first.stop()

    asyncio.run(scenario())


def test_http_requests_pass_through_the_probe() -> None:
    async def scenario() -> int:
        port = free_port()
        listener = UvicornListener(
            create_app(Backend(), console=False), "127.0.0.1", port
        )
        await listener.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /games/x/journal HTTP/1.0\r\n\r\n")
            status = int((await reader.readline()).split()[1])
            writer.close()
            return status
        finally:
            await listener.stop()

    assert asyncio.run(scenario()) == 404
