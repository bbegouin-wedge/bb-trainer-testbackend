# 4 — La console, en lecture

## Objectif

Voir ce qui passe sur les canaux sans lire de JSON brut dans un terminal.

## Le contenu

Les parties en lecture seule de `rawpages/index.html`, en HTMX :

- la liste des matchs ;
- l'en-tête du match : les équipes et l'étape en cours ;
- par coach : l'URL du canal (avec « Copier »), l'état de la socket, rejoint
  ou non, les demandes ouvertes ;
- le fil, mis à jour en direct par un websocket d'observateur, comme
  `/ui/games/{id}/ws` dans automaton, avec ses filtres par coach et par sens.

## Dépend de

Carte 3.

## Terminé quand

Un match joué par l'API de pilotage s'affiche en direct dans la page, sans
rechargement.

## Les tests

`tests/test_console.py` : pages, websocket d'observateur (une poussée par changement), fichiers statiques. Clics réels vérifiés dans Chrome sans fenêtre (CDP).

## Réalisation — à valider

- L'« étape en cours » est un libellé libre (action `phase`), posé par l'opérateur ou le scénario.
- htmx est embarqué (`console/static/`), pour une console qui marche hors ligne.
- Chaque région est une macro de `_regions.html`, dessinée par la page et redessinée par le websocket : aucun gabarit en double.
