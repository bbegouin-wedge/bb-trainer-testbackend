# E01 — La doublure d'automaton

## La fonction

Un serveur qui se fait passer pour automaton sur le canal du coach, pour que
bbTrainer se développe et se teste sans le vrai moteur. Aucune règle de Blood
Bowl n'y vit : ce que le moteur déciderait, c'est l'opérateur qui le décide
dans la console, ou un scénario écrit d'avance.

## Les choix

- FastAPI pour le websocket et les routes HTTP, comme automaton ; console en
  HTMX.
- **Pas de moteur.** Le seul automatisme est le jugement « comme automaton »,
  tiré du catalogue des demandes et des commandes. Ce qu'une étape réelle
  ferait de plus — rouvrir sa demande sur un type inattendu, par exemple — se
  joue à la main ou par scénario.
- **Scénarios en JSON**, rejouables en ligne de commande pour les tests de
  bbTrainer.
- L'état des matchs vit en mémoire : un redémarrage le perd, les scénarios
  le reconstruisent.

## État

Maquettes : `rawpages/index.html` (console), `rawpages/scenarios.html`.

**Cartes 1 à 12 réalisées, à valider** (2026-11-15) : 125 tests, couverture 100 %, comparaison avec automaton `7f5cbae` passée. Rien n'est commité.

## Les cartes

| Carte | Titre | Dépend de | Débloque |
|---|---|---|---|
| 1 | Le socle | — | — |
| 2 | Créer un match et le rejoindre | 1 | bbTrainer se connecte |
| 3 | Les demandes et les commandes | 2 | carte 46 de bbTrainer |
| 4 | La console, en lecture | 3 | voir ce qui passe |
| 5 | La console, aux commandes | 4 | piloter à la main |
| 6 | Les faits | 3 (5 pour l'onglet) | carte 21 de bbTrainer, A3 |
| 7 | Les pannes | 5 | robustesse du client |
| 8 | La conformité du client | 5 | écarts de bbTrainer |
| 9 | Le format des scénarios et le lecteur | 6 | tests automatisés de bbTrainer |
| 10 | Les scénarios dans la console | 9, 5 | rejouer pas à pas |
| 11 | La bibliothèque de scénarios | 9 (7 pour les pannes) | cas limites prêts à l'emploi |
| 12 | Les variantes du protocole | 5 | évolutions avant automaton |
