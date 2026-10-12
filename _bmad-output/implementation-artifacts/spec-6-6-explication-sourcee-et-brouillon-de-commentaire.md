---
title: 'Story 6.6 : Explication sourcée et Brouillon de commentaire'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: '4e59d1b04b5180312bef3d00fd8d64388de4b368'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Le squelette de l'Epic 0 explique déjà chaque Entité rouge ou orange (Citations contrôlées, régénération unique, repli), mais le prompt ne reçoit ni les KPI de l'Entité ni sa répartition des Causes racines (AC 1 de la Story 6.6), le Brouillon est demandé comme un commentaire Jira et non comme le commentaire de la slide, et les phrases retirées ne sont pas journalisées. Aucun test ne vérifie le Brouillon dans l'Excel et le PowerPoint d'un Passage Palier 2 réel.

**Approach:** Compléter la tâche `explication` (`ia/`) : deux nouvelles sections du prompt (KPI de l'Entité à la Date d'arrêté, répartition des Causes racines), lues par `EtapeExplications` via la `Consultation` ; consigne du Brouillon recentrée sur la slide de comité ; journal des phrases retirées. Ajouter un test de bout en bout Palier 2 qui ouvre le xlsx et le pptx publiés.

## Boundaries & Constraints

**Always:** écrire seulement dans `src/usine/ia/` (hors `ia/agent`) et les tests miroirs ; lectures uniquement via le port `Consultation` (`kpi`, `repartition_causes`, `textes_tickets`, `meteo`) ; KPI et Causes racines sont des données entre délimiteurs, comme les tickets ; `version_prompt` reste calculée sur les octets du gabarit envoyé ; prompt en français ; répartition absente (Story 6.5 pas encore livrée, Palier 2 sans étape `repartition_causes`) → section « non disponible », sans erreur.

**Never:** modifier `rendu/`, `contrats/`, `ports/`, la passerelle (`ia/passerelle.py`) ou `ia/controles.py` (6.4 avance en parallèle) ; importer `usine.rendu` depuis `usine.ia` (import-linter) ; recalculer la répartition (AD-9) ; écrire dans Jira.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| KPI présents | `kpi(date, entite)` non vide | section KPI : une ligne `code : valeur` par KPI non ventilé (`dimension == ""`), valeur `n` si dénominateur 1, sinon `n/d` | — |
| KPI absents | table vide | section KPI `- aucun` | — |
| Répartition présente | lignes `cause_racine`, `nombre` | `- cause : nombre`, tri nombre décroissant puis cause | — |
| Répartition absente | table vide (6.5 non livrée) | `- non disponible` | — |
| Phrases retirées | contrôle retire ≥ 1 phrase | warning journalisé : Entité, tentative, nombre retiré / total | — |
| Appel direct sans KPI ni répartition | `expliquer(...)` sans les nouveaux arguments | sections `- aucun` / `- non disponible` (rétrocompatible) | — |

</intent-contract>

## Code Map

- `src/usine/ia/explication.py:180` -- `expliquer` : ajouter les paramètres mot-clé `kpi: pl.DataFrame | None = None`, `repartition: pl.DataFrame | None = None` ; nouvelles variables `kpi`, `causes` dans `rendre_prompt` (qui refuse toute variable manquante ou en trop) ; journal des phrases retirées dans la boucle des tentatives (`resultat.phrases_retirees`). `_donnee` neutralise le délimiteur.
- `src/usine/ia/prompts/explication.md` -- ajouter sections « KPI de l'Entité » et « Causes racines proposées » (dans le bloc de données), consigne du Brouillon : commentaire de la slide de comité, factuel, sans clé hors liste.
- `src/usine/ia/etape.py:40` -- lire `ctx.consultation.kpi(ctx.date_arrete, entite)` et `ctx.consultation.repartition_causes(entite)` par Entité expliquée.
- `src/usine/consultation/passage.py:504` -- (lecture seule) `repartition_causes` rend une table vide au schéma sans fichier ; `kpi` filtre `perimetre == entite`.
- `src/usine/contrats/calcul.py:54` -- (lecture seule) colonnes KPI : `date, perimetre, code_kpi, dimension, numerateur, denominateur`.
- `src/usine/rendu/excel.py:388`, `src/usine/rendu/powerpoint.py:368` -- (lecture seule) Brouillon rendu avec `MENTION_BROUILLON` (`rendu/commun.py:47`), onglet `Commentaires`, slide d'Entité.
- `tests/unit/ia/test_etape.py:30` -- `ConsultationMinimale` : ajouter `kpi` et `repartition_causes`.
- `tests/unit/ia/test_explication.py`, `tests/unit/ia/espions.py` -- tests des nouvelles sections et du journal.
- `tests/unit/chaine/test_execution.py:556,661` -- `test_palier_2_explications`, `_reponses` : base du test de bout en bout xlsx/pptx.

## Tasks & Acceptance

**Execution:**
- `src/usine/ia/explication.py` -- sections KPI et Causes racines, paramètres optionnels, journal des phrases retirées -- AC 1 et 2.
- `src/usine/ia/prompts/explication.md` -- sections et consigne du Brouillon -- AC 1.
- `src/usine/ia/etape.py` -- lecture KPI et répartition par Entité -- AC 1.
- `tests/unit/ia/test_explication.py`, `tests/unit/ia/test_etape.py` -- couvrir la matrice I/O.
- `tests/unit/chaine/test_execution.py` -- test Palier 2 : réponses avec `brouillon_commentaire`, ouvrir `rapport-2026-10-09.xlsx` (onglet Commentaires) et `.pptx` (slide de l'Entité) et y trouver `brouillon IA, à valider : <brouillon>` -- AC 4.

**Acceptance Criteria:**
- Given une Entité rouge ou orange, when l'étape `explications` s'exécute, then le prompt envoyé (pseudonymisé) contient Règles déclenchantes, KPI de l'Entité, tickets en cause et répartition des Causes racines (ou « non disponible »).
- Given une phrase retirée par `controler_citations`, when l'explication se termine, then `phrases_retirees` est porté par la `SortieExplication` et la trace, et un warning le journalise.
- Given un Passage Palier 2 produit avec un Brouillon, when on ouvre l'Excel et le PowerPoint, then le Brouillon figure dans l'onglet Commentaires et sur la slide de l'Entité avec « brouillon IA, à valider », sans modification de `rendu/`.
- Les comportements existants (régénération unique, « explication indisponible », plafond) restent couverts par les tests existants, verts.

## Spec Change Log

## Review Triage Log

### 2026-10-12 — Review pass
- verdicts: 4 findings — high 0, medium 1, low 0, false 3, maybe-false 0
- findings:
  - `[medium]` `[patch]` KPI à dénominateur 0 (« sans objet » selon `domaine/kpi.py`) rendu `0/0` dans le prompt, lisible comme un taux nul — corrigé : `_kpi` écrit `sans objet` ; ligne `KPI-VIDE` ajoutée au test `test_kpi_et_causes_dans_le_bloc_de_donnees`.
  - `[false]` `[reject]` Répartition à plusieurs dates ou causes dupliquées passée à `expliquer` — l'étape passe `Consultation.repartition_causes(entite)`, déjà filtrée sur la Date d'arrêté et l'Entité ; une ligne par (date, Entité, cause) par schéma.
  - `[false]` `[reject]` KPI d'autres Entités ou dates dans le prompt — l'étape passe `Consultation.kpi(ctx.date_arrete, entite)`, filtrée par date et périmètre.
  - `[false]` `[reject]` KPI et Causes à des dates différentes — dans un Passage, `ctx.date_arrete` est la Date d'arrêté du Passage, celle qu'utilise `repartition_causes` (`_date(None)`).

## Design Notes

« Affiché » pour `phrases_retirees` : la valeur est publiée dans `llm/explications.json` et `trace/llm.jsonl` et journalisée ; son affichage dans le Rapport demanderait de toucher `rendu/` (interdit par l'epic) : différé à l'UI Palier 2 (Epic 7). Le formatage des KPI reste brut (`n` ou `n/d`) : `ia` ne peut pas importer `rendu.commun.formater_kpi`.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart
- `uv run pytest -q` -- expected: tout vert

## Auto Run Result

Status: done

**Changement :** la tâche `explication` reçoit désormais les KPI non ventilés de l'Entité à la Date d'arrêté et sa répartition des Causes racines (« non disponible » tant que la 6.5 n'est pas livrée), dans le bloc de données délimité ; le Brouillon est demandé comme commentaire de la slide de comité ; chaque retrait de phrase est journalisé (warning, Entité, tentative, retirées/total). Un test de bout en bout Palier 2 vérifie le Brouillon avec « brouillon IA, à valider » dans l'onglet Commentaires de l'Excel et sur la slide de l'Entité du PowerPoint, sans toucher `rendu/`.

**Fichiers :**
- `src/usine/ia/explication.py` -- sections `kpi` et `causes`, paramètres mot-clé optionnels, journal des retraits.
- `src/usine/ia/prompts/explication.md` -- bloc de données en trois sous-sections, consigne du Brouillon de slide.
- `src/usine/ia/etape.py` -- lecture `kpi` et `repartition_causes` par Entité expliquée.
- `tests/unit/ia/test_explication.py`, `tests/unit/ia/test_etape.py`, `tests/unit/chaine/test_execution.py` -- matrice I/O et test xlsx/pptx.

**Revue (mode économique, Edge Case Hunter seul) :** 4 constats ; 1 patch (medium, KPI 0/0 → « sans objet ») ; 3 rejetés (false, voir Review Triage Log) ; rien de différé. Revue de suivi non recommandée (aucun high, un seul medium).

**Vérification :** `ruff check`, `ruff format --check`, `mypy` (294 fichiers), `lint-imports` (14 contrats) verts ; `pytest -q` : 2445 passés, 1 ignoré, 38 désélectionnés.

**Risques résiduels :** `phrases_retirees` est publié et journalisé mais pas affiché dans le Rapport (toucher `rendu/` est interdit à l'epic) : affichage à prévoir côté UI Palier 2 (Epic 7). Section Causes racines testée de bout en bout seulement en « non disponible » (6.5 non livrée). Changement de prompt → nouvelle `version_prompt`, donc ré-appel des explications au prochain Passage (voulu, FR-14).
