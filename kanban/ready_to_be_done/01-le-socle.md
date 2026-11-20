# 1 — Le socle

## Objectif

Un projet qui démarre et se vérifie, avant la première ligne de protocole.

## Le contenu

- `pyproject.toml` en Python 3.13 (`.python-version` passe de 3.10 à 3.13),
  avec les dépendances d'automaton : fastapi, uvicorn, jinja2, pydantic,
  python-ulid, python-multipart, websockets. En dev : pytest, pytest-cov,
  httpx, ruff, mypy (strict, plugin pydantic).
- Le paquet `testbackend/`, avec `app.py` qui construit l'application FastAPI.
  `main.py` disparaît (il ne fait qu'afficher « Hello »).
- `Makefile` : `serve` (uvicorn), `tests` (ruff format, ruff check --fix,
  mypy, pytest), `check` (les mêmes, sans rien corriger), `help`.
- `tests/scenario.py` : les briques given / when / then communes, dont
  `Attempt` et `then_it_fails_with`, sur le modèle d'automaton.

## Dépend de

Rien.

## Terminé quand

`make serve` démarre un serveur qui répond 404 sur `/`, et `make check` passe
sur un dépôt sans protocole, avec au moins un test exécuté.

## Les tests

Témoin : la suite échoue si elle ne trouve aucun test (pytest), et sous 100 % de couverture.

## Réalisation — à valider

- Python 3.13, outillage d'automaton : ruff, mypy strict, pytest, couverture 100 % lignes et branches.
- `pytest-timeout` (20 s) : une trame attendue qui n'arrive pas fait échouer le test au lieu de le bloquer.
- `make dup` lance jscpd par `npx --no-install`, épinglé dans `package.json` (5.4.2, comme automaton) : il faut `make install` une fois. Pendant la réalisation, le téléchargement n'a pas pu être fait ; un balayage local des blocs de 6 lignes n'a trouvé aucun doublon.
- L'avertissement de Starlette sur `httpx` (remplacé par `httpx2`) reste visible : le changement de dépendance est à décider.
