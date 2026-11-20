"""Le format d'un scénario (`scenarios/*.json`).

    {
      "name": "Avant-match complet",
      "description": "…", "group": "Parcours nominaux", "rule": "R6",
      "game": {"game_id": "…", "home_coach": "…", …},     facultatif
      "settings": {"relay_facts": true},                    facultatif
      "steps": [ … ]
    }

Une étape est l'une de :
- une action (`{"do": …}`), celle de l'API de pilotage ;
- `{"wait": "connect", "coach": "home"}` : attendre la connexion d'un coach ;
- `{"wait": "delay", "seconds": 2}` : laisser passer le temps (une panne qui dure) ;
- `{"wait": "command", "coach": "home", "type": "choose_kick_off",
   "bind": {"choice": "kick_choice"}, "set": {…}, "judge": {…}}` :
  attendre sa prochaine commande, en lier des champs à des variables, en
  déduire d'autres, puis la juger (un Verdict, dont le `then` part avant
  l'accepted) ;
- `{"set": {"kicking_side": {"from": "$kick_choice", "map": {"kick": "home"}}}}`.
Toute étape peut porter une `note` (affichée) ; une attente, un `timeout` en
secondes.

Une valeur `"$nom"` est remplacée par la variable, au moment d'exécuter
l'étape ; `"…$nom…"` dans une chaîne, par son texte.
"""

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from testbackend.actions import Action, Verdict
from testbackend.errors import InvalidInput
from testbackend.ids import Side

VARIABLE = re.compile(r"\$([a-z_][a-z0-9_]*)")
_action: TypeAdapter[Action] = TypeAdapter(Action)


class ScenarioError(Exception):
    """Le scénario ne peut pas continuer : il échoue, avec ce message."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Derive(_Model):
    """Une valeur tirée d'une autre par une table : kick → home."""

    from_: Any = Field(alias="from")
    map: dict[str, Any]


class WaitConnect(_Model):
    wait: Literal["connect"]
    coach: Side
    timeout: float | None = None


class WaitDelay(_Model):
    wait: Literal["delay"]
    seconds: float = Field(ge=0)


class WaitCommand(_Model):
    wait: Literal["command"]
    coach: Side
    type: str | None = None  # attendu ; une autre commande fait échouer
    bind: dict[str, str] = {}  # champ de la commande → variable
    set: dict[str, Any] = {}  # variables déduites, après bind
    judge: dict[str, Any] = {}  # un Verdict, lu après bind et set
    timeout: float | None = None


class SetVars(_Model):
    set: dict[str, Any]


type Step = WaitConnect | WaitDelay | WaitCommand | SetVars | Action


class GameSpec(_Model):
    game_id: str | None = None
    home_coach: str | None = None
    home_team: str | None = None
    visitor_coach: str | None = None
    visitor_team: str | None = None


class Scenario(_Model):
    name: str
    description: str = ""
    group: str = "Divers"
    rule: str = ""  # la règle du client que le scénario éprouve
    game: GameSpec = GameSpec()
    settings: dict[str, Any] = {}
    steps: list[dict[str, Any]]


def parse_step(raw: dict[str, Any]) -> Step:
    """L'étape, une fois ses variables remplacées. `note` est ignorée."""
    data = {k: v for k, v in raw.items() if k != "note"}
    try:
        if "do" in data:
            return _action.validate_python(data)
        if data.get("wait") == "connect":
            return WaitConnect.model_validate(data)
        if data.get("wait") == "command":
            return WaitCommand.model_validate(data)
        if data.get("wait") == "delay":
            return WaitDelay.model_validate(data)
        if "set" in data:
            return SetVars.model_validate(data)
    except ValidationError as err:
        raise ScenarioError(f"étape illisible : {_errors(err)}") from None
    raise ScenarioError(f"étape inconnue : {raw}")


def parse_verdict(raw: dict[str, Any]) -> Verdict:
    try:
        return Verdict.model_validate(raw)
    except ValidationError as err:
        raise ScenarioError(f"jugement illisible : {_errors(err)}") from None


def substitute(value: Any, variables: dict[str, Any]) -> Any:
    """Remplace les `$nom` d'une valeur JSON par les variables."""
    if isinstance(value, dict):
        return {k: substitute(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, variables) for v in value]
    if not isinstance(value, str):
        return value
    if (whole := VARIABLE.fullmatch(value)) is not None:
        return _lookup(whole.group(1), variables)
    return VARIABLE.sub(lambda m: str(_lookup(m.group(1), variables)), value)


def derive(spec: Any, variables: dict[str, Any]) -> Any:
    """La valeur d'une variable de `set` : un littéral, ou une table."""
    value = substitute(spec, variables)
    if not (isinstance(value, dict) and "from" in value):
        return value
    table = Derive.model_validate(value)
    key = str(table.from_)
    if key not in table.map:
        raise ScenarioError(f"{key!r} absent de la table {table.map}")
    return table.map[key]


def load(path: Path) -> Scenario:
    """Lit un scénario, et vérifie dès le chargement les étapes sans variable."""
    try:
        scenario = Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, ValidationError) as err:
        raise InvalidInput(f"{path.name} : scénario illisible : {err}") from None
    for index, raw in enumerate(scenario.steps, start=1):
        if not VARIABLE.search(json.dumps(raw)):
            try:
                parse_step(raw)
            except ScenarioError as err:
                raise InvalidInput(f"{path.name}, étape {index} : {err}") from None
    return scenario


def _lookup(name: str, variables: dict[str, Any]) -> Any:
    if name not in variables:
        raise ScenarioError(f"variable inconnue : ${name}")
    return variables[name]


def _errors(err: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])} : {e['msg']}" for e in err.errors()
    )
