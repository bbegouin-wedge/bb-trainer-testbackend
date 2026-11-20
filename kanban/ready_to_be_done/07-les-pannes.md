# 7 — Les pannes

## Objectif

Provoquer à volonté ce que le réseau et le serveur font de pire, pour éprouver
bbTrainer.

## Le contenu

- Couper une socket, deux ou toutes : 1006 (coupure brutale), 1000 (fermeture
  propre).
- Refuser le prochain accès d'un coach : 403/4403, 404/4404 ; faire échouer
  son arrivée en 500 (socket laissée ouverte, §2).
- Sur la prochaine trame descendante : la perdre, la retarder de n ms, la
  dupliquer.
- Envoyer une Response sans commande en face, ou du texte non JSON.
- Arrêter l'écoute, redémarrer (sockets perdues, matchs gardés).
- L'onglet Pannes de la console.

## Dépend de

Carte 5.

## Terminé quand

Chaque panne est déclenchable depuis la console et l'API de pilotage, et
visible dans le fil.

## Les tests

`tests/test_faults.py` (en mémoire) et `tests/test_library.py` (vrai serveur : coupure brutale et écoute arrêtée, scénarios « reconnexion » et « serveur qui tombe »).

## Réalisation — à valider

- Deux ports : les canaux et la console. « Arrêter l'écoute » coupe les canaux seulement.
- La coupure brutale abandonne le transport TCP (le client voit 1006) ; le transport est capté par un middleware ASGI le plus externe (`server.TransportProbe`).
- Le port est réservé avant uvicorn : sinon un port pris faisait quitter tout le processus (`sys.exit`).
