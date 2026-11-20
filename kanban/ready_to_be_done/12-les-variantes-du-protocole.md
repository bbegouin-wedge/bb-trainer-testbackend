# 12 — Les variantes du protocole

## Objectif

Tester bbTrainer contre les évolutions proposées du protocole (§9 de la spec)
avant qu'automaton les livre.

## Le contenu

Chacune derrière un réglage de la console :

1. `reply_to` et `request_id` dans la commande : la doublure sert la demande
   désignée, refuse une demande périmée.
2. `id` de commande repris dans la Response.
3. Le message `hello` à la connexion, avec la version du protocole.
4. Le `code` métier dans `refused`.

## Dépend de

Carte 5.

## Terminé quand

Chaque variante se règle depuis la console et a ses tests.

## Les tests

`tests/test_variants.py` : chaque variante, et les champs typés qu'elle ajoute.

## Réalisation — à valider

- Réalisée malgré « à n'ouvrir que si… » : le coût était faible une fois le protocole isolé dans `protocol.py`.
- `hello` annonce `protocol: 1`, comme l'exemple de la §9.
