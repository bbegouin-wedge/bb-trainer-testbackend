# 9 — Le format des scénarios et le lecteur

## Objectif

Rejouer un match écrit d'avance, sans opérateur, notamment dans la CI de
bbTrainer.

## Le contenu

- Le schéma JSON d'un scénario (`scenarios/*.json`) : un nom, une liste
  d'étapes :
  - attendre la connexion d'un coach ;
  - attendre une commande d'un coach : son `type`, son jugement (comme
    automaton, toujours accepter, accepter et rouvrir, refuser avec un code,
    demander à l'opérateur), un délai maximal, les variables à lier
    (`"bind": {"choice": "$kick_choice"}`) ;
  - ouvrir une demande, émettre un ou plusieurs faits (dont « avant
    l'`accepted` ») ;
  - provoquer une panne ;
  - terminer le match.
- Les variables (`$nom`), et une table de correspondance pour en déduire une
  autre (`kick` → `home`).
- Le lecteur : d'un trait ou pas à pas ; un scénario se lance sur un match
  existant ou en crée un.
- Le lancement en ligne de commande, `make serve SCENARIO=…` : le serveur joue
  le scénario et sort en 0 s'il va au bout, en 1 sinon (délai dépassé,
  commande inattendue), avec le fil en sortie.
- Un scénario d'exemple : l'avant-match complet.

## Dépend de

Carte 6 (les faits, que les scénarios émettent).

## Terminé quand

L'avant-match complet se joue en ligne de commande face à deux clients de
test, et sort en 0 ; un client qui ne répond pas le fait sortir en 1.

## Les tests

`tests/test_scenarios.py` (lecteur, variables, échecs) et `tests/test_cli.py` (code de sortie, ligne `ready`, arrêt, `--keep`, port pris).

## Réalisation — à valider

- Une commande d'un autre type que celui attendu fait **échouer** le scénario ; elle est jugée comme automaton pour ne pas bloquer le client.
- La CI de bbTrainer lit la ligne JSON `ready` (match et `coach_id`) ; un scénario peut aussi fixer ses identifiants (`game`).
- Étape ajoutée : `{"wait": "delay"}`, pour une panne qui dure.
- Avant de s'arrêter, le serveur vide les files d'envoi : le `finished` part toujours.
