# 2 — Créer un match et le rejoindre

## Objectif

Que bbTrainer ouvre ses deux canaux sur la doublure comme sur automaton, et
reçoive l'accusé de sa jonction. Réseau seul : aucune page.

## Le contenu

Les sections 2 et 3 de la spec, sans les demandes (carte 3) :

- **`POST /games`** : corps `home_coach`, `home_team`, `visitor_coach`,
  `visitor_team` (ULID), coachs et équipes distincts, sinon 422. Rend
  `{"game_id": …}` en 201. Les ULID absents sont tirés par la doublure, pour
  créer un match d'un simple `curl`.
- **Le canal** `ws://{host}/games/{game_id}/coaches/{coach_id}/ws`, messages
  JSON texte :
  - admission : match inconnu → `refused` 404 puis fermeture 4404 ; coach qui
    ne joue pas ce match → `refused` 403 puis fermeture 4403 ;
  - première connexion : le serveur traite `join_game` pour ce coach et envoie
    `{"type": "accepted", "command": {"type": "join_game", "coach_id": …}}` ;
  - reconnexion : il renvoie les demandes encore ouvertes de ce coach (aucune
    tant que la carte 3 n'est pas faite) ;
  - un seul écrivain par socket : tout ce qui descend passe par une file.
- **Le fil** : chaque trame montante et descendante, et chaque ouverture ou
  fermeture de socket, enregistrée avec son heure et son coach.
  `GET /games/{id}/journal` le rend en JSON ; 404 pour un match inconnu.
- L'état des matchs en mémoire.

## Dépend de

Carte 1.

## Terminé quand

Un match créé par `POST /games` : deux clients websocket (tests, puis
bbTrainer) rejoignent chacun leur canal et reçoivent leur `accepted` ; un
coach étranger et un match inconnu sont refusés avec le bon code de fermeture ;
une reconnexion ne renvoie pas de second `accepted`. Le journal montre tout.

## Les tests

`tests/test_joining.py` (canal, en mémoire) ; `tests/contract/` : la même suite d'échanges contre la doublure (à chaque `make test`) et contre automaton (`make check-automaton`) — admission 404/4404 et 403/4403, jonction, reconnexion, au mot près.

## Réalisation — à valider

- `POST /games` rend seulement `game_id`, comme automaton ; `POST /pilot/games` rend aussi les deux places.
- La jonction émet le fait `coach_joined`, comme l'étape `pending_coaches` : relayé si le relais est actif (carte 6).
- Vérifié contre automaton `7f5cbae` : la suite de comparaison passe des deux côtés.
