# 11 — La bibliothèque de scénarios

## Objectif

Les cas que bbTrainer doit savoir traiter, prêts à jouer.

## Le contenu

- Parcours nominaux : avant-match complet ; placement d'une équipe (A3).
- Cas limites du protocole : demande rouverte sur une commande d'un type
  inattendu ; reconnexion en pleine demande ; demande reçue deux fois ; deux
  demandes ouvertes (409 ambigu) ; refus de placement motivé (`rejected`, A3).
- Pannes : coach refusé (4403) ; match inconnu (4404) ; serveur qui tombe.

Chaque scénario dit, dans sa description, la règle du client qu'il éprouve.

## Dépend de

Carte 9 ; carte 7 pour les scénarios de pannes.

## Terminé quand

Chaque scénario se joue en ligne de commande face à un client de test qui
suit la spec, et sort en 0.

## Les tests

`tests/test_library.py` : chaque scénario sur le vrai serveur, face à deux **clients de référence** (`tests/reference_client.py`, qui suit la §6) → sortie 0.

## Réalisation — à valider

- Neuf scénarios : avant-match, placement (A3), demande rouverte, reconnexion, demande doublée, deux demandes, coach refusé, match inconnu, serveur qui tombe.
- Le client de référence a montré que R4 et R7 se combinent : le dédoublonnage vaut pour une connexion ; à la reconnexion, l'état repart du rattrapage.
