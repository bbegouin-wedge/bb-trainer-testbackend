# 5 — La console, aux commandes

## Objectif

Piloter un match à la main depuis la console, sans passer par l'API HTTP.

## Le contenu

- Créer un match depuis la page.
- Le composeur : onglets Demande (modèles tirés du catalogue, `request_id`
  suivant ou imposé, remplacer ou garder la demande de même `key`, envoyer
  deux fois), Fin du match, Trame brute.
- Les actions sur une demande ouverte : rouvrir, fermer.
- Le mode de jugement : manuel ou automatique.
- En manuel, la file des commandes à juger, avec les contrôles du catalogue
  affichés, et les verdicts : accepter et clore, accepter et rouvrir,
  accepter puis enchaîner (le composeur, dont les envois partent avant
  l'`accepted`), refuser en 409 (n'attend rien ou ambiguë), 422 ou 500.
  Un message illisible reste refusé en 422 sans passer par l'opérateur.

## Dépend de

Carte 4.

## Terminé quand

Un avant-match complet se joue depuis la console seule, bbTrainer en face,
en jugement manuel.

## Les tests

`tests/test_console.py` : chaque verdict, les actions attachées (« avant l'accepted »), l'abandon d'une commande quand son coach part, les réglages invalides.

## Réalisation — à valider

- « Accepter puis enchaîner » : le composeur a un sélecteur « Envoyer : maintenant / avant l'accepted de la commande n°… ». Pas de bouton dédié.
- La console n'a aucune route d'écriture : elle appelle l'API de pilotage (extension htmx `json-body`, `console.js`).
- Un verdict retire la commande de l'attente sur-le-champ, et rend une promesse tenue quand sa Response est partie : un scénario ne peut ni juger deux fois, ni doubler l'accepted (deux courses trouvées et corrigées).
