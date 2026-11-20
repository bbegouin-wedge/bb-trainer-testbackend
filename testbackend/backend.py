"""Le service de la doublure : tout ce qui change un match passe par ici.

Le canal du coach, l'API de pilotage, la console et les scénarios n'ont pas
d'autre accès à l'état. Tout tourne dans une seule boucle asyncio, sans
thread : deux opérations ne se croisent jamais, et un même enchaînement
d'appels donne toujours les mêmes trames, dans le même ordre.

Chaque trame descendante passe par `_deliver`, qui l'écrit au fil, applique
la panne armée et la dépose dans la file des sockets du coach. Chaque
changement est signalé (`_changed`) : la console se redessine, un scénario
qui attend reprend.
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, assert_never

from pydantic import BaseModel, ConfigDict, ValidationError

from testbackend import conformity
from testbackend.actions import (
    Action,
    CloseRequest,
    Cut,
    EmitFact,
    Finish,
    FrameFault,
    Listening,
    OpenRequest,
    RefuseAccess,
    ReopenRequest,
    SendRaw,
    SetPhase,
    Target,
    Verdict,
)
from testbackend.catalog import Catalog, load_catalog
from testbackend.errors import Conflict, InvalidInput, UnknownGame
from testbackend.game import Coach, Game, Level, QueuedFact, Request, WireEntry
from testbackend.ids import SIDES, Side, parse_id
from testbackend.judge import Serve, like_automaton, served_request
from testbackend.protocol import (
    Refusal,
    Uplink,
    Variants,
    accepted_frame,
    ambiguous,
    encode,
    fact_frame,
    finished_frame,
    hello_frame,
    not_a_coach,
    not_waiting,
    parse_uplink,
    refused_frame,
    request_frame,
    server_error,
    unknown_game,
    unreadable,
)

type JudgeMode = Literal["auto", "manual", "scenario"]


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: JudgeMode = "auto"
    relay_facts: bool = False  # à venir A3 : les faits relayés aux coachs
    catch_up_requests: bool = True  # §2 : les demandes ouvertes à la reconnexion
    reconnect_timeout_s: float = 5.0  # R7
    variants: Variants = Variants()


@dataclass(frozen=True, slots=True)
class Close:
    """Dans la file d'une socket : la fermer, brutalement ou proprement."""

    mode: Literal["abrupt", "clean"]


type Outgoing = tuple[str, float] | Close


class Channel:
    """Une socket ouverte : ce qui descend (outbox) et ce qui monte (inbox)."""

    def __init__(self) -> None:
        self.outbox: asyncio.Queue[Outgoing] = asyncio.Queue()
        self.inbox: asyncio.Queue[str] = asyncio.Queue()


@dataclass(frozen=True, slots=True)
class Admission:
    side: Side
    fail_arrival: bool


class Listener(Protocol):
    """L'écoute des canaux, que la panne « serveur qui tombe » arrête."""

    @property
    def listening(self) -> bool: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class Backend:
    def __init__(
        self,
        catalog: Catalog | None = None,
        clock: Callable[[], float] = time.time,
        listener: Listener | None = None,
    ) -> None:
        self.catalog = catalog or load_catalog()
        self.clock = clock
        self.listener = listener
        # L'adresse des canaux, telle que bbTrainer la connaît : posée au lancement.
        self.channels_url = "ws://127.0.0.1:8000"
        self.settings = Settings()
        self.games: dict[str, Game] = {}
        self._channels: dict[tuple[str, Side], list[Channel]] = {}
        self._access_faults: dict[tuple[str, Side], int] = {}
        self._frame_faults: dict[tuple[str, Side], FrameFault] = {}
        self._verdicts: dict[tuple[str, int], asyncio.Future[Verdict]] = {}
        # Tenue quand la Response d'une commande jugée est partie.
        self._settled: dict[tuple[str, int], asyncio.Future[None]] = {}
        self._tick = asyncio.Event()

    # --- Matchs ---------------------------------------------------------------

    def game(self, game_id: str) -> Game:
        if game_id not in self.games:
            raise UnknownGame(game_id)
        return self.games[game_id]

    def create_game(
        self,
        game_id: str | None = None,
        home_coach: str | None = None,
        home_team: str | None = None,
        visitor_coach: str | None = None,
        visitor_team: str | None = None,
    ) -> Game:
        """Crée un match ; un identifiant absent est tiré au hasard."""
        gid = parse_id(game_id, "game_id")
        coaches = {
            "home": Coach(
                "home",
                parse_id(home_coach, "home_coach"),
                parse_id(home_team, "home_team"),
            ),
            "visitor": Coach(
                "visitor",
                parse_id(visitor_coach, "visitor_coach"),
                parse_id(visitor_team, "visitor_team"),
            ),
        }
        if coaches["home"].coach_id == coaches["visitor"].coach_id:
            raise InvalidInput("les deux coachs doivent être différents")
        if coaches["home"].team_id == coaches["visitor"].team_id:
            raise InvalidInput("les deux équipes doivent être différentes")
        if gid in self.games:
            raise Conflict(f"le dossier {gid} est déjà démarré")
        game = Game(gid, coaches)  # type: ignore[arg-type]
        self.games[gid] = game
        self._wire(game, None, "sys", "match créé")
        self._changed(game)
        return game

    def update_settings(self, changes: dict[str, Any]) -> Settings:
        merged = {**self.settings.model_dump(), **changes}
        if "variants" in changes:
            merged["variants"] = {
                **self.settings.variants.model_dump(),
                **changes["variants"],
            }
        try:
            self.settings = Settings.model_validate(merged)
        except ValidationError as err:
            raise InvalidInput(
                f"réglages invalides : {err.errors(include_url=False)}"
            ) from None
        for game in self.games.values():
            self._changed(game)
        return self.settings

    # --- Le canal du coach ----------------------------------------------------

    def admit(self, game_id: str, coach_id: str) -> Admission | Refusal:
        """L'admission d'un canal (§2), et la panne d'accès armée s'il y en a une."""
        game = self.games.get(game_id)
        if game is None:
            return unknown_game(game_id)
        side = game.side_of(coach_id)
        if side is None:
            return not_a_coach(game_id, coach_id)
        status = self._access_faults.pop((game_id, side), None)
        if status in (403, 404):
            self._wire(
                game,
                side,
                "sys",
                f"accès refusé ({status})",
                note="panne armée",
                level="warn",
            )
            self._changed(game)
            return (
                not_a_coach(game_id, coach_id)
                if status == 403
                else unknown_game(game_id)
            )
        return Admission(side, fail_arrival=status == 500)

    def open_channel(
        self, game_id: str, side: Side, channel: Channel, fail_arrival: bool
    ) -> None:
        """L'arrivée (§2) : jonction au premier accès, rattrapage ensuite."""
        game = self.game(game_id)
        coach = game.coaches[side]
        coach.sockets += 1
        self._channels.setdefault((game_id, side), []).append(channel)
        self._check_reconnection(game, coach)
        game.script.append({"wait": "connect", "coach": side})
        first = "premier accès" if not coach.joined else "reconnexion"
        self._wire(game, side, "sys", f"socket ouverte · admis · {first}")
        if fail_arrival:
            self._send(
                game,
                side,
                refused_frame(server_error(), self.settings.variants),
                only=channel,
                note="panne armée : arrivée en échec, socket laissée ouverte",
                level="warn",
            )
        else:
            self._arrive(game, coach, channel)
        self._changed(game)

    def close_channel(
        self, game_id: str, side: Side, channel: Channel, code: int | None
    ) -> None:
        game = self.game(game_id)
        coach = game.coaches[side]
        self._channels[(game_id, side)].remove(channel)
        coach.sockets -= 1
        self._wire(
            game, side, "sys", f"socket fermée ({code})" if code else "socket fermée"
        )
        if not coach.connected:
            for pending in [p for p in game.pending if p.side == side]:
                self._verdicts[(game_id, pending.number)].cancel()
            game.in_flight[side] = 0
        self._changed(game)

    def received(self, game_id: str, side: Side, raw: str) -> None:
        """Un message vient d'être lu : on le date, avant tout traitement (R2)."""
        game = self.game(game_id)
        self._wire(game, side, "up", _uplink_label(raw), text=raw)
        game.exercised.add("R2")
        if game.in_flight[side] > 0:
            conformity.note(
                game,
                "R2",
                side,
                self.clock(),
                "commande envoyée avant la Response de la précédente",
            )
        game.in_flight[side] += 1
        self._changed(game)

    async def process(self, game_id: str, side: Side, raw: str) -> None:
        """Traite un message lu. Les messages d'un canal passent un par un."""
        game = self.game(game_id)
        variants = self.settings.variants
        try:
            uplink = parse_uplink(raw, self.catalog, variants)
            game.exercised.add("422")
            if isinstance(uplink, Refusal):
                conformity.note(game, "422", side, self.clock(), uplink.detail)
                self._send(game, side, refused_frame(uplink, variants))
                return
            self._observe(game, side, uplink)
            verdict, number = await self._verdict_for(game, side, uplink)
            game.script.append(_wait_command_step(side, uplink, verdict))
            try:
                await self._apply_verdict(game, side, uplink, verdict)
            finally:
                settled = self._settled.pop((game.game_id, number), None)
                if settled is not None:
                    settled.set_result(None)
        finally:
            game.in_flight[side] = max(0, game.in_flight[side] - 1)
            self._changed(game)

    # --- Jugement manuel ou par scénario ---------------------------------------

    def judge(
        self, game_id: str, number: int, verdict: Verdict
    ) -> "asyncio.Future[None]":
        """Rend le verdict d'une commande. Elle quitte l'attente sur-le-champ :
        juger deux fois la même est impossible, même avant son traitement.
        Rend une promesse tenue quand sa Response est partie."""
        future = self._verdicts.pop((game_id, number), None)
        if future is None or future.done():
            raise Conflict(f"aucune commande n°{number} à juger")
        game = self.game(game_id)
        pending = game.find_pending(number)
        assert pending is not None
        game.pending.remove(pending)
        future.set_result(
            verdict.model_copy(update={"then": [*pending.staged, *verdict.then]})
        )
        self._changed(game)
        return self._settled[(game_id, number)]

    def stage(self, game_id: str, number: int, action: Action) -> None:
        """Attache une action à une commande à juger : elle part avant son accepted."""
        pending = self.game(game_id).find_pending(number)
        if pending is None:
            raise Conflict(f"aucune commande n°{number} à juger")
        pending.staged.append(action)
        self._changed(self.game(game_id))

    async def wait_for[T](
        self, predicate: Callable[[], T | None], timeout: float | None = None
    ) -> T:
        """Attend qu'un changement rende le prédicat non nul ; lève TimeoutError."""
        async with asyncio.timeout(timeout):
            while True:
                tick = self._tick
                value = predicate()
                if value is not None and value is not False:
                    return value
                await tick.wait()

    # --- Actions ----------------------------------------------------------------

    async def apply(self, game_id: str, action: Action, record: bool = True) -> None:
        """Applique une action. `record` : un geste de l'opérateur, à garder pour
        le fil en scénario (False pour ce qu'un verdict enchaîne)."""
        game = self.game(game_id)
        if record:
            game.script.append(
                action.model_dump(mode="json", exclude_defaults=True)
                | {"do": action.do}
            )
        match action:
            case OpenRequest():
                self._open_request(game, action)
            case ReopenRequest(key=key, options=options):
                old = self._existing(game, key)
                game.close_request(old)
                self._announce(
                    game,
                    game.add_request(key, {**old.options, **(options or {})}, None),
                )
            case CloseRequest(key=key):
                request = self._existing(game, key)
                game.close_request(request)
                self._wire(
                    game, None, "sys", f"demande close : {key} #{request.request_id}"
                )
            case EmitFact(fact=fact, to=to, seq=seq, queued=queued):
                self._emit_fact(game, fact, _targets(to), seq, queued)
            case Finish(output=output):
                self._flush_queued(game)
                game.finished = True
                game.requests.clear()
                for side in SIDES:
                    self._send(game, side, finished_frame(output))
            case SetPhase(label=label):
                game.phase = label
            case SendRaw(to=to, text=text):
                self._deliver(
                    game,
                    to,
                    text,
                    "trame brute",
                    note="envoyée sans contrôle",
                    level="warn",
                )
            case Cut(to=to, mode=mode):
                self._cut(game, _targets(to), mode)
            case RefuseAccess(to=to, status=status):
                self._access_faults[(game_id, to)] = status
                self._wire(
                    game,
                    to,
                    "sys",
                    f"panne armée : prochain accès en {status}",
                    level="warn",
                )
            case FrameFault(to=to):
                self._frame_faults[(game_id, to)] = action
                self._wire(
                    game,
                    to,
                    "sys",
                    f"panne armée : prochaine trame {_fault_label(action)}",
                    level="warn",
                )
            case Listening(on=on):
                await self._listen(game, on)
            case _:
                assert_never(action)
        self._changed(game)

    async def drain(self, timeout: float = 2.0) -> None:
        """Attend que tout ce qui est en file soit parti (avant un arrêt)."""
        queues = [ch.outbox.join() for chs in self._channels.values() for ch in chs]
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*queues)
        except TimeoutError:
            pass  # une socket bloquée ne retient pas l'arrêt

    # --- Lecture ----------------------------------------------------------------

    def conformity(self, game_id: str) -> list[conformity.RuleReport]:
        return conformity.report(
            self.game(game_id), self.clock(), self.settings.reconnect_timeout_s
        )

    def snapshot(self, game_id: str) -> dict[str, Any]:
        """Le match entier, en JSON : `GET /games/{id}/journal`."""
        game = self.game(game_id)
        return {
            "game_id": game.game_id,
            "phase": game.phase,
            "finished": game.finished,
            "coaches": {
                side: {
                    "coach_id": c.coach_id,
                    "team_id": c.team_id,
                    "joined": c.joined,
                    "connected": c.connected,
                }
                for side, c in game.coaches.items()
            },
            "requests": [
                {"key": r.key, "request_id": r.request_id, "options": r.options}
                for r in game.requests
            ],
            "facts": [{"seq": f.seq, "fact": f.fact} for f in game.facts],
            "pending": [
                {"number": p.number, "side": p.side, "command": p.uplink.command}
                for p in game.pending
            ],
            "wire": [
                {
                    "at": e.at,
                    "side": e.side,
                    "direction": e.direction,
                    "kind": e.kind,
                    "text": e.text,
                    "note": e.note,
                    "level": e.level,
                }
                for e in game.wire
            ],
            "conformity": [
                {
                    "rule": r.rule.id,
                    "title": r.rule.title,
                    "status": r.status,
                    "deviations": [
                        {"side": d.side, "detail": d.detail} for d in r.deviations
                    ],
                }
                for r in self.conformity(game_id)
            ],
        }

    # --- Interne : l'arrivée ------------------------------------------------------

    def _arrive(self, game: Game, coach: Coach, channel: Channel) -> None:
        if self.settings.variants.hello:
            self._send(game, coach.side, hello_frame(), only=channel)
        if self.settings.relay_facts:
            for fact in game.facts:
                self._send(
                    game,
                    coach.side,
                    fact_frame(fact.seq, fact.fact),
                    only=channel,
                    note="rattrapage",
                )
        if not coach.joined:
            coach.joined = True
            self._emit_fact(
                game,
                {
                    "type": "coach_joined",
                    "side": coach.side,
                    "coach_id": coach.coach_id,
                },
                list(SIDES),
                None,
                False,
            )
            join = {"type": "join_game", "coach_id": coach.coach_id}
            self._send(
                game,
                coach.side,
                accepted_frame(join, None),
                only=channel,
                note="Response de l'arrivée : traitée par le serveur",
                level="ok",
            )
        elif self.settings.catch_up_requests:
            for request in game.requests_for(coach.side):
                self._send(
                    game,
                    coach.side,
                    request_frame(request.key, request.request_id, request.options),
                    only=channel,
                    note="rattrapage",
                )

    def _check_reconnection(self, game: Game, coach: Coach) -> None:
        if coach.cut_at is None:
            return
        late = self.clock() - coach.cut_at
        if late > self.settings.reconnect_timeout_s:
            conformity.note(
                game, "R7", coach.side, self.clock(), f"reconnecté après {late:.1f} s"
            )
        coach.cut_at = None

    # --- Interne : les commandes ---------------------------------------------------

    def _observe(self, game: Game, side: Side, uplink: Uplink) -> None:
        """Les écarts qu'une commande lisible peut révéler (R3, join_game)."""
        game.exercised |= {"R3", "JOIN"}
        now = self.clock()
        if uplink.type == "join_game":
            conformity.note(game, "JOIN", side, now, "join_game envoyé par le client")
        candidates = game.requests_for(side)
        if not candidates:
            conformity.note(
                game, "R3", side, now, f"{uplink.type} sans demande ouverte"
            )
        elif all(
            r.accepts is not None and uplink.type not in r.accepts for r in candidates
        ):
            conformity.note(game, "R3", side, now, f"{uplink.type} absent de accepts")

    async def _verdict_for(
        self, game: Game, side: Side, uplink: Uplink
    ) -> tuple[Verdict, int]:
        """Le verdict de la commande, et son numéro (-1 sans jugement)."""
        if self.settings.judge == "auto":
            return Verdict(), -1
        pending = game.add_pending(side, uplink, self.clock())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Verdict] = loop.create_future()
        self._verdicts[(game.game_id, pending.number)] = future
        self._settled[(game.game_id, pending.number)] = loop.create_future()
        self._changed(game)
        try:
            verdict = await future
        except asyncio.CancelledError:
            self._wire(
                game,
                side,
                "sys",
                f"commande n°{pending.number} abandonnée : socket fermée",
                level="warn",
            )
            raise
        finally:
            if pending in game.pending:  # abandonnée avant d'être jugée
                game.pending.remove(pending)
                del self._verdicts[(game.game_id, pending.number)]
                del self._settled[(game.game_id, pending.number)]
        return verdict, pending.number

    async def _apply_verdict(
        self, game: Game, side: Side, uplink: Uplink, verdict: Verdict
    ) -> None:
        variants = self.settings.variants
        outcome = self._outcome(game, side, uplink, verdict)
        if isinstance(outcome, Refusal):
            self._send(game, side, refused_frame(outcome, variants, uplink.command_id))
            return
        if outcome.request is not None:
            game.close_request(outcome.request)
        for action in verdict.then:
            await self.apply(game.game_id, action, record=False)
        if outcome.reopen and outcome.request is not None:
            request = outcome.request
            self._announce(game, game.add_request(request.key, request.options, None))
        self._send(game, side, accepted_frame(uplink.command, uplink.command_id))

    def _outcome(
        self, game: Game, side: Side, uplink: Uplink, verdict: Verdict
    ) -> Serve | Refusal:
        variants = self.settings.variants
        match verdict.kind:
            case "like_automaton":
                return like_automaton(game, side, uplink, variants)
            case "refuse":
                return self._refusal(game, side, verdict.refusal)
            case _:
                served = served_request(game, side, uplink, variants)
                request = served if isinstance(served, Request) else None
                return Serve(request, reopen=verdict.kind == "accept_reopen")

    def _refusal(self, game: Game, side: Side, kind: str) -> Refusal:
        keys = [r.key for r in game.requests_for(side)]
        return {
            "not_waiting": not_waiting(game.game_id),
            "ambiguous": ambiguous(game.game_id, game.coaches[side].coach_id, keys),
            "unreadable": unreadable(["refusé par l'opérateur"]),
        }.get(kind, server_error())

    # --- Interne : demandes et faits ------------------------------------------------

    def _open_request(self, game: Game, action: OpenRequest) -> None:
        options = {
            k: v for k, v in action.options.items() if k not in ("to", "coach_id")
        }
        if action.to != "any":
            options = {
                "to": "coach",
                "coach_id": game.coaches[action.to].coach_id,
                **options,
            }
        if action.replace and (old := game.find_request(action.key)) is not None:
            game.close_request(old)
        request = game.add_request(action.key, options, action.request_id)
        self._announce(game, request, times=2 if action.twice else 1)

    def _announce(self, game: Game, request: Request, times: int = 1) -> None:
        self._flush_queued(game)
        recipients = request.recipients(game)
        if not recipients:
            self._wire(
                game,
                None,
                "sys",
                f"demande {request.key} sans destinataire",
                level="warn",
            )
        frame = request_frame(request.key, request.request_id, request.options)
        for side in recipients:
            for _ in range(times):
                self._send(game, side, frame)

    def _existing(self, game: Game, key: str) -> Request:
        request = game.find_request(key)
        if request is None:
            raise Conflict(f"aucune demande {key} ouverte")
        return request

    def _emit_fact(
        self,
        game: Game,
        fact: dict[str, Any],
        targets: list[Side],
        seq: int | None,
        queued: bool,
    ) -> None:
        if errors := self.catalog.check_fact(fact):
            raise InvalidInput(f"fait mal formé : {errors}")
        if queued:
            game.queued_facts.append(QueuedFact(fact, targets, seq))
            self._wire(game, None, "sys", f"fait en file : {fact['type']}")
            return
        added = game.add_fact(fact, seq)
        if not self.settings.relay_facts:
            self._wire(
                game,
                None,
                "sys",
                f"fait #{added.seq} {fact['type']} tenu au journal",
                note="relais des faits coupé",
            )
            return
        for side in targets:
            self._send(game, side, fact_frame(added.seq, added.fact))

    def _flush_queued(self, game: Game) -> None:
        queued, game.queued_facts = game.queued_facts, []
        for q in queued:
            self._emit_fact(game, q.fact, q.targets, q.seq, False)

    # --- Interne : pannes -------------------------------------------------------------

    def _cut(
        self, game: Game, sides: list[Side], mode: Literal["abrupt", "clean"]
    ) -> None:
        game.exercised.add("R7")
        for side in sides:
            channels = self._channels.get((game.game_id, side), [])
            if not channels:
                self._wire(
                    game, side, "sys", "coupure : aucune socket ouverte", level="warn"
                )
                continue
            game.coaches[side].cut_at = self.clock()
            for channel in channels:
                channel.outbox.put_nowait(Close(mode))
            label = "brutale" if mode == "abrupt" else "propre (1000)"
            self._wire(
                game,
                side,
                "sys",
                f"coupure {label}",
                note="panne provoquée",
                level="warn",
            )

    async def _listen(self, game: Game, on: bool) -> None:
        if self.listener is None:
            raise Conflict("l'écoute des canaux ne se pilote pas ici")
        if on:
            await self.listener.start()
        else:
            await self.listener.stop()
        self._wire(
            game,
            None,
            "sys",
            "écoute relancée" if on else "écoute arrêtée",
            level="warn",
        )

    # --- Interne : le fil -----------------------------------------------------------

    def _send(
        self,
        game: Game,
        side: Side,
        frame: dict[str, Any],
        only: Channel | None = None,
        note: str = "",
        level: Level = "info",
    ) -> None:
        self._deliver(game, side, encode(frame), _frame_label(frame), only, note, level)

    def _deliver(
        self,
        game: Game,
        side: Side,
        text: str,
        label: str,
        only: Channel | None = None,
        note: str = "",
        level: Level = "info",
    ) -> None:
        channels = [only] if only else self._channels.get((game.game_id, side), [])
        if not channels:
            self._wire(game, side, "down", label, text, "perdue : coach absent", "warn")
            return
        fault = self._frame_faults.pop((game.game_id, side), None)
        if fault is not None and fault.fault == "drop":
            self._wire(game, side, "down", label, text, "perdue : panne", "warn")
            return
        delay = (
            fault.delay_ms / 1000
            if fault is not None and fault.fault == "delay"
            else 0.0
        )
        copies = 2 if fault is not None and fault.fault == "duplicate" else 1
        for channel in channels:
            for _ in range(copies):
                channel.outbox.put_nowait((text, delay))
        if fault is not None:
            note, level = f"panne : {_fault_label(fault)}", "warn"
        self._wire(game, side, "down", label, text, note, level)

    def _wire(
        self,
        game: Game,
        side: Side | None,
        direction: Literal["down", "up", "sys"],
        kind: str,
        text: str = "",
        note: str = "",
        level: Level = "info",
    ) -> None:
        game.wire.append(
            WireEntry(self.clock(), side, direction, kind, text, note, level)
        )

    def touch(self, game_id: str) -> None:
        """Signale un changement venu d'ailleurs (l'état d'un scénario)."""
        self._changed(self.game(game_id))

    def _changed(self, game: Game) -> None:
        game.version += 1
        tick, self._tick = self._tick, asyncio.Event()
        tick.set()


def _wait_command_step(side: Side, uplink: Uplink, verdict: Verdict) -> dict[str, Any]:
    step: dict[str, Any] = {"wait": "command", "coach": side, "type": uplink.type}
    judge = verdict.model_dump(mode="json", exclude_defaults=True)
    if verdict.then:
        judge["then"] = [
            a.model_dump(mode="json", exclude_defaults=True) | {"do": a.do}
            for a in verdict.then
        ]
    if judge:
        step["judge"] = judge
    return step


def _targets(to: Target) -> list[Side]:
    return list(SIDES) if to == "both" else [to]


def _fault_label(fault: FrameFault) -> str:
    return {"drop": "perdue", "duplicate": "doublée"}.get(
        fault.fault, f"retardée de {fault.delay_ms} ms"
    )


def _frame_label(frame: dict[str, Any]) -> str:
    match frame:
        case {"type": "request", "key": key, "request_id": rid}:
            return f"request {key} #{rid}"
        case {"type": "refused", "status": status}:
            return f"refused {status}"
        case {"type": "accepted", "command": {"type": command}}:
            return f"accepted {command}"
        case {"type": "fact", "seq": seq, "fact": {"type": fact}}:
            return f"fact #{seq} {fact}"
        case _:
            return str(frame["type"])


def _uplink_label(raw: str) -> str:
    try:
        return f"command {json.loads(raw)['command']['type']}"
    except (ValueError, TypeError, KeyError):
        return "message illisible"
