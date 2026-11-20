"""Un client de référence : ce que la §6 de la spec attend d'un client.

- R1/R2 : une commande à la fois ; la suivante attend la Response de la
  précédente.
- R3 : il ne répond qu'à une demande ouverte, avec un type de `accepts`
  (le premier, rempli par l'exemple du catalogue, et le premier des `choices`).
- R4 : une demande déjà reçue (même key, même request_id) est ignorée.
- R7 : à chaque connexion, l'état repart de ce que le serveur renvoie
  (rattrapage) : rien n'est gardé de la connexion précédente.
- R6 : il écoute tout le temps.
- R7 : une socket coupée, ou un accès refusé, se rouvre après une courte pause.
Il s'arrête sur `finished`, ou à l'échéance.

Il tourne dans un thread, sur de vrais websockets : c'est le banc de test
de bout en bout de la doublure, et un exemple exécutable pour bbTrainer.
"""

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from testbackend.catalog import load_catalog

CATALOG = load_catalog()


@dataclass
class ReferenceClient:
    url: str
    deadline: float = 30.0
    received: list[dict[str, Any]] = field(default_factory=list)
    sent: list[dict[str, Any]] = field(default_factory=list)
    connections: int = 0
    finished: bool = False
    error: str = ""
    _thread: threading.Thread | None = None

    def start(self) -> "ReferenceClient":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def join(self, timeout: float | None = None) -> None:
        assert self._thread is not None
        self._thread.join(timeout)

    def _run(self) -> None:
        end = time.monotonic() + self.deadline
        while not self.finished and time.monotonic() < end:
            try:
                with connect(self.url, open_timeout=2) as ws:
                    self.connections += 1
                    self._listen(ws, end)
            except (OSError, ConnectionClosed, TimeoutError):
                time.sleep(0.1)  # R7 : on rouvre
        if not self.finished:
            self.error = "pas de finished avant l'échéance"

    def _listen(self, ws: ClientConnection, end: float) -> None:
        in_flight = False
        waiting: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        while time.monotonic() < end:
            try:
                frame = json.loads(ws.recv(timeout=0.2))
            except TimeoutError:
                continue
            self.received.append(frame)
            match frame:
                case {"type": "finished"}:
                    self.finished = True
                    return
                case {"type": "refused", "status": 403 | 404}:
                    return  # la socket se ferme : on rouvrira
                case {"type": "accepted" | "refused"}:
                    in_flight = False
                case {"type": "request", "key": key, "request_id": rid} if (
                    key,
                    rid,
                ) not in seen:
                    seen.add((key, rid))
                    waiting = [r for r in waiting if r["key"] != key] + [frame]
            if not in_flight and waiting:
                command = _answer(waiting.pop(0))
                if command is not None:
                    try:
                        ws.send(json.dumps({"command": command}))
                    except ConnectionClosed:
                        continue  # on lit d'abord ce qui reste reçu
                    self.sent.append(command)
                    in_flight = True


def _answer(request: dict[str, Any]) -> dict[str, Any] | None:
    accepts = request["options"].get("accepts") or []
    if not accepts:
        return None
    command = {"type": accepts[0], **CATALOG.commands[accepts[0]].example()}
    choices = request["options"].get("choices")
    if choices and "choice" in command:
        command["choice"] = choices[0]
    return command
