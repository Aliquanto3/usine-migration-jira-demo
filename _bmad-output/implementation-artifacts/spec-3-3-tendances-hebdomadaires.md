---
title: 'Story 3.3 : Tendances hebdomadaires'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'b382e2eb3b42d549fc27535dff5329cecbcf36a6'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-3-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** FR-12 exige des Tendances hebdomadaires sur 8 semaines (valeur du dernier Jour ouvré, Entrées et Sorties cumulées) ; aucune fonction du domaine ne les produit, `tendances.parquet` reste vide et le Pilote ne peut pas montrer la trajectoire de l'usine en comité.

**Approach:** Ajouter à `domaine/kpi.py` une fonction pure `tendances(kpi, date_arrete, ancrage)` qui agrège la table `SCHEMA_KPI` par semaine du Programme (`semaine_programme`) en table `SCHEMA_TENDANCE` : pour chaque semaine, tous les KPI au dernier Jour ouvré présent (≤ Date d'arrêté), plus les codes `entrees_semaine` et `sorties_semaine` cumulés sur la semaine.

## Boundaries & Constraints

**Always:** fonction pure en Polars (AD-9) ; semaines via `contrats.calendrier.semaine_programme(d, ancrage)` seulement, ancrage passé par l'appelant (AD-17) ; entiers `numerateur`/`denominateur`, aucun flottant (AD-10) ; entrée validée par `valider(…, SCHEMA_KPI)`, sortie par `valider(…, SCHEMA_TENDANCE)` ; lignes postérieures à la Date d'arrêté ignorées (indépendance au futur) ; erreurs en `UsineErreur`, message en français nommant la valeur fautive ; ordre des lignes déterministe.

**Never:** modifier `src/usine/contrats/`, `src/usine/ports/`, `src/usine/chaine/` (branchement de l'étape : lane L5) ou `tests/unit/domaine/constructeur.py` ; ajouter une dépendance ou un nouveau module hors `domaine/kpi.py` (carte des lanes) ; inventer une valeur pour une semaine sans Jour ouvré dans la table ; recalculer un KPI depuis les états des tickets.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Semaine complète | KPI du lundi 28/09 au vendredi 02/10 (semaine 1, ancrage 28/09), D = 02/10 | une ligne par (périmètre, code, dimension) de date 02/10, valeurs du 02/10 | — |
| Cumul | `entrees_jour` 1, 0, 2, 0, 1 et `sorties_jour` 0, 1, 1, 0, 0 sur la semaine | `entrees_semaine` 4/1, `sorties_semaine` 2/1, dimension `""` | — |
| Semaine partielle | KPI jusqu'au mercredi 07/10 (semaine 2), D = 07/10 | semaine 2 datée du 07/10, valeurs du 07/10, cumul du lundi au mercredi | — |
| Futur ignoré | table jusqu'au 09/10, D = 07/10 | résultat identique à la table tronquée au 07/10 | — |
| Plus de 8 semaines | KPI des semaines 1 à 10, D en semaine 10 | semaines 3 à 10 seulement (8 dernières) | — |
| Semaine sans jour | table commençant en semaine 2, D en semaine 3 | semaines 2 et 3 seulement, aucune ligne pour la semaine 1 | — |
| Date d'arrêté absente | D hors des dates de la table | — | `UsineErreur` nommant D |
| Code inconnu | `code_kpi` hors de `CODES_KPI` | — | `UsineErreur` nommant le code |
| Date avant l'ancrage | une date de la table < ancrage, ou ancrage pas un lundi | — | `UsineErreur` de `semaine_programme` |
| Table vide | aucune ligne | table vide au `SCHEMA_TENDANCE` (D non exigée) | — |

</intent-contract>

## Code Map

- `src/usine/domaine/kpi.py` -- seul fichier source : `CODES_KPI` (l. 56), `ENTREES_JOUR`/`SORTIES_JOUR` (l. 39-40) à réutiliser ; ajouter constantes `ENTREES_SEMAINE`, `SORTIES_SEMAINE`, `CODES_TENDANCE`, `NOMBRE_SEMAINES_TENDANCE = 8` et la fonction `tendances`.
- `src/usine/contrats/calcul.py` -- `SCHEMA_TENDANCE` (mêmes colonnes que `SCHEMA_KPI`, toutes non nulles ; `date` = dernier Jour ouvré de la semaine, partielle comprise), lecture seule.
- `src/usine/contrats/calendrier.py:104` -- `semaine_programme(d, ancrage)` (1 = semaine de l'ancrage ; refuse ancrage non lundi et date antérieure), lecture seule.
- `src/usine/contrats/evenements.py:115` -- `EnteteJournal.ancrage_semaines` : origine de l'ancrage côté appelant.
- `src/usine/consultation/passage.py:346` et `src/usine/contrats/agent.py:88` (`PointTendance`) -- consommateurs du format, lecture seule.
- `tests/unit/domaine/test_kpi.py` -- ajouter les tests (fixtures `generation`/`etats_generes` l. 303-314 et helpers `_ts`, `Flux` déjà là) ; le contrôle des lanes n'autorise pas de `test_tendances.py` plat.

## Tasks & Acceptance

**Execution:**
- `src/usine/domaine/kpi.py` -- ajouter `tendances(kpi: pl.DataFrame, date_arrete: date, ancrage: date) -> pl.DataFrame` : validation, filtre `date ≤ date_arrete`, semaine de chaque date, conservation des 8 dernières semaines jusqu'à celle de D, valeurs au dernier jour de chaque semaine, cumuls `entrees_semaine`/`sorties_semaine` depuis `entrees_jour`/`sorties_jour`, tri -- FR-12, AD-9, AD-10, AD-17.
- `tests/unit/domaine/test_kpi.py` -- un test par ligne de la matrice, plus sur le Journal du générateur : schéma validé sans flottant, déterminisme (ordre compris), semaines 1 à 8 présentes avec D = `date_injection`, valeurs de semaine égales aux KPI du dernier jour, cumuls égaux à la somme des `entrees_jour`/`sorties_jour`.

**Acceptance Criteria:**
- Given les KPI quotidiens de l'historique (8 semaines), when le domaine calcule les Tendances, then chaque semaine 1 à 8 (`semaine_programme` de sa `date`) porte tous les KPI de son dernier Jour ouvré et ses Entrées et Sorties cumulées.
- Given une Date d'arrêté en milieu de semaine, when on calcule la semaine en cours, then elle est datée de la Date d'arrêté et en porte les valeurs.
- Given les cinq contrôles du dépôt, when on les lance, then ruff, ruff format, mypy, lint-imports et pytest passent.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 23 findings — high 0, medium 0, low 19, false 4, maybe-false 0
- findings:
  - `[low]` `[reject]` (intent) Lecture « résultat visible du Pilote » : `tendances.parquet` non écrit — l'écriture du Passage appartient à `chaine` (lane L5, Epic 5) selon le contexte de l'Epic 3 ; la story livre la fonction du domaine.
  - `[low]` `[reject]` (intent) Fenêtre glissante au-delà de la semaine 8 (semaines 3 à 10) — inatteignable avec l'historique nominal de 8 semaines (FR-2) où l'on obtient bien 1 à 8 ; choix écrit dans les Design Notes.
  - `[low]` `[reject]` (intent) Erreur si la Date d'arrêté n'a pas de ligne au lieu d'un repli — `kpi` couvre chaque Jour ouvré de l'historique ; un repli masquerait une erreur d'appel.
  - `[low]` `[patch]` (edge) Ancrage contrôlé aussi sur les dates hors fenêtre, contrairement à la docstring — docstring de `tendances` corrigée (dates de la table ≤ D).
  - `[low]` `[reject]` (edge) Dates non ouvrées en entrée — `kpi` les refuse en amont (`_verifier_dates`) ; garde supplémentaire pour un cas inatteignable.
  - `[low]` `[reject]` (edge) Clés en double en entrée — `kpi` produit une ligne par clé ; garde pour un cas inatteignable.
  - `[low]` `[reject]` (edge) Table vide avec un ancrage non lundi acceptée — sans date, aucun numéro de semaine n'est calculé ; résultat vide correct.
  - `[false]` `[reject]` (edge) `date_arrete` en `datetime` — la signature exige `date` (mypy) ; appelant fautif hors contrat.
  - `[low]` `[reject]` (edge) Périmètre absent du dernier jour de la semaine — sortie `kpi` dense : chaque périmètre est présent à chaque date.
  - `[low]` `[reject]` (edge, claim) « dernier Jour ouvré » sans contrôle `est_jour_ouvre` — même cause que les dates non ouvrées, garanties par `kpi`.
  - `[low]` `[reject]` (blind) Numéro de semaine absent de la sortie — `SCHEMA_TENDANCE` est gelé (contrats-v1) et définit `date` comme porteuse ; le numéro se retrouve par `semaine_programme(date, ancrage)`.
  - `[low]` `[reject]` (blind) Semaines hors 1 à 8 — même groupe que la fenêtre glissante (intent).
  - `[low]` `[reject]` (blind) Doublons non détectés — même groupe que les clés en double (edge).
  - `[low]` `[reject]` (blind) Week-end non refusé — même groupe que les dates non ouvrées.
  - `[low]` `[reject]` (blind) Cumuls dépendants des périmètres du dernier jour — même groupe que le périmètre absent.
  - `[low]` `[reject]` (blind) Branche `fill_null(0)` non testée — inatteignable avec une sortie `kpi` dense.
  - `[low]` `[reject]` (blind) Ordre dépendant de l'ordre d'entrée — l'entrée `kpi` est triée de façon déterministe ; l'ordre de sortie reproduit le sien (Entités puis Programme).
  - `[false]` `[reject]` (blind) Ancrage contrôlé hors fenêtre — doublon du constat edge déjà corrigé par la docstring ; le comportement (refus) est voulu.
  - `[false]` `[reject]` (blind) `max(1, …)` sans effet — faux : pour `s < 8`, `s − 7` est ≤ 0 et `max` borne la première semaine à 1 ; résultat identique au filtre mais valeur exacte.
  - `[low]` `[reject]` (blind) Dimensions non validées — sortie `kpi` limitée à `DIMENSIONS_KPI` ; garde pour un cas inatteignable.
  - `[low]` `[patch]` (blind) `sorties_semaine` de la semaine partielle non vérifié — fixture avec Sorties non nulles et assertions (3/1 et 1/1).
  - `[false]` `[reject]` (blind) Fonction non branchée dans la Chaîne — hors lane (L5) ; énoncé dans les Never de la spec.
  - `[low]` `[patch]` (verification) Branche « Date d'arrêté antérieure à toutes les dates » non testée — `test_tendance_date_d_arrete_anterieure` ajouté.

## Design Notes

**Catalogue** : `CODES_TENDANCE` = `CODES_KPI` puis `entrees_semaine`, `sorties_semaine` (dimension `""`, dénominateur 1). Tous les KPI sont repris au dernier jour (lecture littérale de FR-12 ; le consommateur filtre par `code_kpi`). Pas de colonne de semaine : le contrat la porte par `date`, le numéro se retrouve par `semaine_programme(date, ancrage)`.

**Ordre** : semaine croissante, puis périmètre dans l'ordre de première apparition dans la table d'entrée (Entités puis `PROGRAMME` avec `kpi`), puis code dans l'ordre de `CODES_TENDANCE`, puis dimension dans l'ordre d'apparition (tri stable).

**Fenêtre de 8 semaines** : semaines `max(1, s − 7)` à `s`, où `s` = semaine de D. Une semaine sans aucune date dans la table n'a pas de ligne. Le cumul porte sur les dates présentes de la semaine, jusqu'à D.

## Verification

**Commands:**
- `uv run pytest -q tests/unit/domaine` -- expected: tous verts
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: succès

## Auto Run Result

- **Résumé :** fonction pure `tendances(kpi_quotidiens, date_arrete, ancrage)` dans `domaine/kpi.py` : table `SCHEMA_TENDANCE` des 8 dernières semaines du Programme jusqu'à la Date d'arrêté (numérotées par `semaine_programme`), chaque semaine portant tous les KPI de son dernier Jour ouvré (semaine en cours datée de la Date d'arrêté) et les cumuls `entrees_semaine`/`sorties_semaine`, en entiers.
- **Fichiers :**
  - `src/usine/domaine/kpi.py` -- constantes `ENTREES_SEMAINE`, `SORTIES_SEMAINE`, `CODES_TENDANCE`, `NOMBRE_SEMAINES_TENDANCE` et fonction `tendances`.
  - `tests/unit/domaine/test_kpi.py` -- 13 tests : matrice, ordre, Date d'arrêté antérieure, Journal du générateur (semaines 1 à 8, valeurs du dernier jour, cumuls, déterminisme).
- **Revue :** 23 findings ; 3 corrigés (patch, tous `low` : docstring du contrôle d'ancrage, test de la Date d'arrêté antérieure, assertion de `sorties_semaine` en semaine partielle) ; 0 différé ; 20 rejetés (16 low, 4 false), motifs dans le Review Triage Log.
- **Revue de suivi recommandée :** non (patches : 0 high, 0 medium, 3 low).
- **Vérification :** `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` (1232 passés, 1 sauté) : tous verts. Audit de matrice : chaque ligne couverte par un test passé.
- **Risques résiduels :** l'étape `tendances` de la Chaîne (lane L5) reste à brancher, en passant `EnteteJournal.ancrage_semaines` ; le numéro de semaine n'est pas une colonne (contrat gelé) et se recalcule par `semaine_programme(date, ancrage)` ; au-delà de 8 semaines d'historique, la fenêtre glisse (semaines 3 à 10, par exemple).
- **Fichiers hors lane :** aucun.
