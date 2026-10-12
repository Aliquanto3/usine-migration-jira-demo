# Journal du run autonome (vague 1, puis vague 2 jusqu'avant la porte M3)

Run lancé le 2026-10-12, en l'absence d'Anaël (au moins 6 h). Point de départ : `main` à l'étiquette `contrats-v1` (CI verte sous Windows et Linux).

## Règles du run

- Une lane = un worktree sous `../usine-lanes/lane-<n>-<nom>`, branche `lane/<n>-<nom>`. Stories passées une à une par `bmad-build-auto`.
- Fusion dans `main` sérialisée : `main` fusionné dans la lane, contrôles complets (ruff, format, mypy, lint-imports, pytest, contrôle des lanes), puis avance rapide de `main`.
- `contrats/` et `ports/` sont gelés : une story qui doit les modifier s'arrête et entre dans la file humaine.
- Story arrêtée : son travail est conservé sur une branche `bloque/<story>`, la lane s'arrête, les stories qui en dépendent sont sautées.
- Hors du run : 1.6, 1.7, 2.7 (Jira Cloud), 5.7 (porte M3), Epic 6 et suivantes.
- Aucun push, aucune étiquette.

## Stories

| Story | Lane | Statut | Commit sur `main` | Résumé |
|---|---|---|---|---|
| 8.1 | L8 (`lane-8-portage`) | done | `824fba1` | Fiche d'une page `docs/fiche-outillage.md` : demandes priorisées, correspondance par brique rattachée à AD-1, AD-19 et NFR-8, points d'attention par cible, avec un test de structure. |

## File humaine

## Fichiers écrits hors lane
