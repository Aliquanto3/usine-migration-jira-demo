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
| 3.1 | L3 (`lane-3-calcul`) | done | `03182ed` | Instantanés complets : dédoublonnage par `id_evenement`, refus des dates hors Jours ouvrés, ordre canonique des lignes par `rang_cle`, tests de propriété (futur sans effet) et de déterminisme. |
| 2.1 | L2 (`lane-2-extraction`) | done | `10a7e5e` | Paquet `adaptateurs/jira_http` : transport commun (authentification Cloud et DC, reprise sur 429 avec `Retry-After`, pagination par jeton et par position), `ClientJiraLecture` à liste blanche vérifiée avant envoi et `ClientJiraEcriture` distinct ; fixtures synthétiques, à remplacer par de vrais enregistrements à la recette 2.7. |
| 8.1 (revue de suivi) | L8 (`lane-8-portage`) | done | `f337372` | 27 constats, 4 correctifs : entrepôt DuckDB dans le portage Dataiku, accès GitHub au modèle spaCy pour la VM, pseudonymisation rattachée à AD-1, garde de `_section` ; fiche à 696 mots, travail convergé. |
| 2.1 (revue de suivi) | L2 (`lane-2-extraction`) | done | `2f4fc06` | 31 constats, 5 correctifs : garde AST + grimp du client d'écriture (imports relatifs, `._transport`, accès dynamiques) à la place de la seule recherche textuelle, `httpx.InvalidURL` en `UsineErreur`, exposant de reprise borné ; sondes hôte toutes sur le site ; travail convergé. |
| 3.2 | L3 (`lane-3-calcul`) | done | `b29755a` | `domaine/kpi.py` : douze KPI quotidiens denses (stocks, Entrées/Sorties du jour et sur la Fenêtre glissante, âges médian et maximum, taux de KO et de non-exécution, Certifications) par Entité et Programme, en entiers `numerateur`/`denominateur`, depuis l'état des tickets. |
| 3.3 | L3 (`lane-3-calcul`) | done | `34504bf` | `domaine/kpi.py` : `tendances(kpi, date_arrete, ancrage)` rend les 8 dernières semaines du Programme (`semaine_programme`), chaque semaine portant les KPI de son dernier Jour ouvré (semaine en cours datée de la Date d'arrêté) et les cumuls `entrees_semaine`/`sorties_semaine`. |
| 1.1 | L1 (`lane-1-donnees`) | done | `e393071` | `config/programme.yaml` complet (« Banque Exemple — migration SI cœur », 10 Entités, 3 Vagues et leurs Phases, volumétrie cible) ; le générateur applique bornes d'Entrées par semaine et calendrier des Phases, tire la clé de projet de `ConfigJira.cle_projet` et le lundi de `contrats.calendrier` (constat 12). |
| 2.2 | L2 (`lane-2-extraction`) | done | `69a967e` | Paquet `adaptateurs/jira_cloud` : `SourceJiraCloud` lit Jira Cloud par le seul `ClientJiraLecture` (recherche JQL avec changelog, complément par ticket des changelogs tronqués) et émet des `Evenement` canoniques selon `config/jira.yaml` ; suite de contrat `SourceTickets` exécutée sur Cloud depuis la lane (fabrique dans `tests/contrat/` à ajouter par PR courte sur `main`). |

## File humaine

## Fichiers écrits hors lane

- Story 1.1 (L1) : `tests/unit/chaine/environnement.py`, `tests/contrat/consultation/fabriques.py`, `tests/contrat/source_tickets/fabriques.py`, `tests/unit/adaptateurs/journal/test_source_journal.py`, `tests/unit/domaine/test_instantanes.py`, `tests/unit/domaine/test_meteo.py` : passage à la fixture réduite `tests/unit/generateur/programme_reduit.yaml` (une ou deux lignes chacun), indispensable car la configuration complète porte la suite à plus de 10 min et casse les attendus ENT-A/ENT-B.
