# 3 — Les demandes et les commandes

## Objectif

Le cycle complet demande → commande → Response, piloté par HTTP. C'est ce
dont la carte 46 de bbTrainer (« Parler à automaton ») a besoin.

## Le contenu

- **Le catalogue** (`testbackend/data/catalog.json`), recopié de la §5 de la
  spec : les demandes connues (`kick_off_choice`…) avec leurs `options` types,
  et les commandes du coach avec leurs champs (`join_game`, `choose_kick_off`).
  Il remplace les modèles pydantic d'automaton pour décider du 422. Il se met
  à jour à la main quand automaton évolue.
- **L'API de pilotage** (HTTP, en attendant la console) :
  - ouvrir une demande pour un coach, ou pour n'importe lequel (sans `to`) :
    `key`, `options` ; `request_id` suivant du match, ou imposé ;
  - rouvrir une demande (même `key`, nouveau `request_id`), la fermer ;
  - terminer le match : `finished` aux coachs connectés.
- **Une demande ouverte est poussée** au coach visé s'il est connecté, et
  renvoyée à sa reconnexion.
- **Le jugement « comme automaton »**, pour chaque `{"command": …}` reçu :
  - illisible (JSON invalide, `type` inconnu du catalogue, champ manquant ou
    en trop, valeur hors du type) → `refused` 422 ;
  - aucune demande ouverte pour ce coach → `refused` 409 ;
  - plusieurs → `refused` 409 (demande ambiguë) ;
  - sinon → la demande est close, `accepted` avec la commande telle quelle.
  Les commandes d'un canal sont traitées une par une.
- **Ordre** : ce qu'ouvre le traitement d'une commande part avant son
  `accepted` (§3). L'API de pilotage peut donc attacher, à une demande
  ouverte, la suite à envoyer quand elle sera servie.

## Dépend de

Carte 2.

## Terminé quand

Le « Terminé quand » de la carte 46 de bbTrainer passe contre la doublure :
deux instances rejoignent leur canal, une demande `kick_off_choice` ouverte
par HTTP arrive au bon coach, sa commande revient `accepted` ; les 409 et 422
sont couverts par des tests.

## Les tests

`tests/test_requests.py` : chaque refus de la §7, l'ordre (ce qu'ouvre une commande part avant son accepted), le rattrapage, la fin. Comparaison avec automaton : 409, 422, kick_off_choice, rattrapage.

## Réalisation — à valider

- Le jugement « comme automaton » sert l'unique demande ouverte ; une commande d'un type absent de `accepts` est acceptée **et la demande rouverte**, comme le font les étapes livrées (`decide_kicking_team`, `set_up_team`).
- Une demande `to: any` part sans `to` aux deux coachs (`ForAnyCoach`).
- Les actions de pilotage sont un seul modèle (`testbackend/actions.py`) : l'API, la console, les verdicts et les scénarios s'en servent tous.
