# 8 — La conformité du client

## Objectif

Que la doublure dise d'elle-même où bbTrainer s'écarte des règles du client
(§6 de la spec).

## Le contenu

Les contrôles observables côté serveur :

- R2 : une commande envoyée avant la Response de la précédente ;
- R3 : une commande sans demande ouverte, ou d'un type absent de `accepts` ;
- un message illisible (422) ;
- un `join_game` envoyé par le client, alors que le serveur le traite à la
  connexion ;
- R7 : pas de reconnexion après une coupure provoquée (délai à fixer).

R4 (ignorer une demande reçue deux fois) n'est pas observable côté serveur :
la console le dit, et renvoie au journal de bbTrainer.

Le panneau « Conformité du client » de la console, l'écart noté dans le fil,
et le décompte dans `GET /games/{id}/journal`.

## Dépend de

Carte 5.

## Terminé quand

Chaque contrôle a un test qui le voit passer et un qui le voit échouer.

## Les tests

`tests/test_conformity.py` : chaque règle vue passer et vue échouer, R7 à l'horloge (fausse) : à temps, en retard, jamais.

## Réalisation — à valider

- Délai de R7 : 5 s par défaut, réglable.
- Une demande sans `accepts` ne donne pas d'écart R3 sur le type.
- R4 est affichée « non observable » : seul le journal de bbTrainer la montre.
