.DEFAULT_GOAL := help
SHELL := /bin/bash
export NO_COLOR := 1

AUTOMATON ?= ../automaton

.PHONY: help install test lint format typecheck dup check tests serve play check-automaton

help:  ## Liste les cibles
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-16s %s\n", $$1, $$2}'

# --- Portes : vérifient sans jamais corriger -----------------------------------

install:  ## Installe les dépendances (uv.lock, et jscpd par npm)
	uv sync --locked
	npm install --no-audit --no-fund --loglevel=error

test:  ## Suite complète, échoue sous 100 % de couverture
	uv run pytest -q -p no:cacheprovider --cov

lint:  ## Linters et vérification du formatage (ne corrige rien)
	uv run ruff check --no-cache --output-format concise .
	uv run ruff format --check --no-cache .

typecheck:  ## Typage statique (mypy strict)
	uv run mypy .

dup:  ## Code dupliqué (jscpd, réglages dans .jscpd.json)
	npx --no-install jscpd --no-colors

check-automaton:  ## Compare la doublure au vrai automaton (AUTOMATON=chemin du dépôt)
	AUTOMATON_DIR=$(abspath $(AUTOMATON)) uv run pytest -q -p no:cacheprovider -m contract tests/contract

# --- Confort --------------------------------------------------------------------

format:  ## Applique le formatage et les corrections automatiques de ruff
	uv run ruff format .
	uv run ruff check --fix .

check: lint typecheck dup test  ## Tout ce que la CI doit lancer (sans corriger)

tests: format typecheck dup test  ## Avant livraison : corrige le style, puis vérifie tout

serve:  ## Canaux sur :8000, console sur http://127.0.0.1:8001 (JUDGE=manual…)
	uv run python -m testbackend $(if $(JUDGE),--judge $(JUDGE)) $(ARGS)

play:  ## Joue un scénario et rend son verdict : SCENARIO=scenarios/x.json
	$(if $(SCENARIO),,$(error SCENARIO requis : chemin du scénario))
	uv run python -m testbackend --scenario $(SCENARIO) $(ARGS)
