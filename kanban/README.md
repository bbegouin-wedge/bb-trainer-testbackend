# Kanban — bb-testbackend

Une carte par fichier, `NN-slug.md`, numérotée dans l'ordre de création. Son
statut est son dossier ; on la déplace avec `git mv`.

| Dossier | Sens |
|---|---|
| `to_be_refined/` | l'intention est posée, le contenu reste à préciser |
| `ready_to_be_done/` | prête : contenu et « Terminé quand » validés |
| `done/` | faite, et validée par l'utilisateur |
| `cancelled/` | abandonnée, avec la raison écrite dans la carte |
| `epics/` | les regroupements de cartes |

Une carte porte : **Objectif**, **Le contenu**, **Dépend de**, **Terminé
quand**, et **Pourquoi à raffiner** tant qu'elle n'est pas prête.

Référence du protocole imité :
`../bloodbowltrainer/docs/protocole-client-serveur.md` (v0, automaton `7f5cbae`).
Maquettes : `rawpages/`.
