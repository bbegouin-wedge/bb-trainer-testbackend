# bb-testbackend — la doublure d'automaton

Un serveur qui se fait passer pour [automaton](../automaton) sur le canal du
coach, pour développer et tester bbTrainer sans le vrai moteur. Il parle le
protocole de `../bloodbowltrainer/docs/protocole-client-serveur.md` (v0) :
même adresse, mêmes trames, mêmes refus, au mot près.

**Aucune règle de Blood Bowl n'y vit.** Ce que le moteur déciderait, c'est
l'opérateur qui le décide dans la console, ou un scénario écrit d'avance.

## Démarrer

```bash
make install        # uv sync, et jscpd par npm (make dup)
make serve          # canaux sur ws://127.0.0.1:8000, console sur http://127.0.0.1:8001
make serve JUDGE=manual          # chaque commande attend un verdict de l'opérateur
```

Un match se crée depuis la console (« + Nouveau »), ou comme le fait
bloodbowlclub.com : `curl -X POST localhost:8000/games -d '{}' -H 'content-type: application/json'`.
La console affiche, pour chaque coach, l'URL du canal à donner à bbTrainer.

## La console

- **Les coachs** : socket, demandes ouvertes (rouvrir, fermer), commandes à
  juger (comme automaton, accepter, accepter et rouvrir, 409, 422, 500), pannes.
- **Le composeur** : ouvrir une demande, émettre un fait, terminer le match,
  envoyer une trame brute, nommer l'étape. « Envoyer : avant l'accepted de la
  commande n°… » attache l'envoi au verdict d'une commande en attente.
- **Les réglages** : mode de jugement, rattrapage des demandes, relais des
  faits (à venir A3), variantes proposées du protocole (§9), délai de R7.
- **La conformité du client** : les règles de la §6 que le serveur peut
  observer (R2, R3, 422, join_game, R7), avec chaque écart.
- **Le fil** : chaque trame, montante et descendante, et ce qui l'explique.
  « En scénario » exporte les gestes du match en scénario rejouable.

Tout ce que fait la console passe par l'API de pilotage (`/pilot/…`), que
n'importe quel banc de test peut appeler de même.

## Les scénarios

Des fichiers JSON dans `scenarios/` (format : `testbackend/scenario/model.py`).
La page « Scénarios » les joue, d'un trait ou pas à pas. En ligne de commande :

```bash
make play SCENARIO=scenarios/avant-match.json
```

Le serveur écrit une ligne JSON `ready` (le match et ses deux `coach_id`),
joue le scénario face aux clients qui se connectent, et sort en 0 s'il va au
bout, 1 sinon. C'est le point d'entrée prévu pour la CI de bbTrainer.

## Vérifier

```bash
make tests             # formate, puis typage, doublons, tests (100 % de couverture)
make check             # la même chose, sans rien corriger
make check-automaton   # la même suite d'échanges contre le vrai automaton (AUTOMATON=../automaton)
```

Le plan et son avancement : `kanban/`. Les maquettes d'origine : `rawpages/`.
