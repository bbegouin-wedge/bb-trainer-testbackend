# 6 — Les faits

## Objectif

Envoyer à bbTrainer les faits du match, tels qu'automaton les relaiera avec
le ticket A3 `relay_facts_to_coaches`.

## Le contenu

- Le catalogue des faits de la §5 de la spec (`game_started`, `team_fetched`,
  `coach_joined`, `dice_rolled`, `fan_factor_determined`,
  `weather_determined`, `roll_off_won`, `kicking_team_chosen`), complété au
  fil d'A3 (`player_placed`, `player_reserved`…).
- `{"type": "fact", "seq": n, "fact": {…}}`, `seq` à partir de 0 ; `seq`
  imposé possible, pour créer un trou ou un doublon.
- Envoi aux deux coachs ou à un seul ; mise en file, pour partir avant la
  prochaine demande.
- Le réglage « relais des faits » : désactivé, les faits restent dans le
  journal (automaton aujourd'hui) ; activé, ils partent en direct, et tous
  sont envoyés à chaque connexion, avant la jonction ou les demandes.
- Dans la console : l'onglet Fait et le tableau des faits.

## Dépend de

Carte 3 ; carte 5 pour l'onglet de la console.

## Terminé quand

Relais activé, une reconnexion reçoit tous les faits dans l'ordre des `seq`,
avant ses demandes ouvertes.

## Les tests

`tests/test_facts.py` : relais coupé ou actif, `seq` imposé, faits en file, rattrapage à chaque connexion avant les demandes, faits mal formés (422).

## Réalisation — à valider

- Format pris dans le ticket A3 `relay_facts_to_coaches` tel qu'au commit lu ; à recaler quand automaton le livrera.
- Les faits A3 (`player_placed`, `player_reserved`, `team_set_up`) sont au catalogue, marqués « à venir A3 ».
