# 10 — Les scénarios dans la console

## Objectif

Lancer, suivre et éditer un scénario depuis la console
(`rawpages/scenarios.html`).

## Le contenu

- La bibliothèque : les fichiers de `scenarios/`, par groupe.
- Le déroulé : les étapes faites, l'étape en cours, les écarts survenus.
- Lecture, pas à pas, rejouer depuis le début, choix du match.
- L'édition d'une étape, et l'ajout d'étapes.
- L'import du fil de la console comme scénario.
- Le mode de jugement « Scénario » de la console.

## Dépend de

Cartes 9 et 5.

## Terminé quand

Un scénario se crée depuis le fil d'un match joué à la main, s'enregistre, et
se rejoue pas à pas.

## Les tests

`tests/test_scenarios.py` : bibliothèque (fichiers illisibles compris), page, websocket, export du fil puis relecture.

## Réalisation — à valider

- Les fichiers sont la seule source : la page lit et joue, elle n'édite pas. Un scénario s'écrit en exportant le fil d'un match joué à la main (« En scénario »), puis en retouchant le fichier.
- L'export se fait à partir des gestes du match (connexions, commandes jugées, actions), pas des trames : il se rejoue tel quel.
