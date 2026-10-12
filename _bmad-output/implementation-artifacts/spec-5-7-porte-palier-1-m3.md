---
title: 'Story 5.7 : Porte Palier 1 (M3)'
type: 'chore'
created: '2026-10-13'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-12-contrats-1-2.md'
warnings: []
deferred: []
baseline_revision: '16eba05c9cb8f2d3b540c619168ef9e891d3f17a'
---

<intent-contract>

## Intent

**Problem:** la porte M3 n'est pas passée : la mesure NFR-2 du README date de la Story 1.3 (étapes `extraction`, `kpi`, `prevision` encore bouchons), le Rejeu n'est prouvé que sur une source composite simulée, et aucun journal de fin de jalon M3 n'existe. L'Epic 6 (déjà avancé de 6.1 à 6.7) attend cette porte.

**Approach:** remesurer NFR-2 avec `outils/mesurer_nfr2.py` (étapes réelles) et sur `DEMO` réel (extraction incrémentale comprise) ; extraire la comparaison du Rejeu de `test_rejeu.py` dans un outil `outils/verifier_rejeu.py` réutilisé par le test et exécuté sur deux Passages composites réels de même date ; rejouer la réconciliation ; consigner le tout dans `docs/journal-jalon-m3.md`.

## Boundaries & Constraints

**Always:** Palier 1, aucun appel LLM réel ; Jira en lecture seule ; exécutions réelles depuis le dépôt principal (`donnees/`, secrets), code et doc dans le worktree `lane/5-rapport` ; `contrats/` et `ports/` intacts ; `EXCLUSIONS_REJEU` inchangé ; test de Rejeu existant toujours aussi strict (mêmes `DIFFERENCES_ATTENDUES`).

**Never:** lire ou afficher `.env` ; écrire dans Jira ; versionner un Passage ou `donnees/` ; pousser (la CI verte est vérifiée par l'orchestrateur sur le SHA intégré) ; trancher SM-10 ou AD-16 (arbitrages d'Anaël, seulement consignés).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rejeu conforme | deux Passages de même date, seuls des champs exclus diffèrent | code 0, liste des différences exclues observées | — |
| Rejeu non conforme | une différence hors `EXCLUSIONS_REJEU` | code 1, différences fautives listées `fichier : champ` | — |
| Fichier absent d'un seul côté | un rendu présent dans un seul Passage | différence `<fichier>` signalée, code 1 | — |
| Date sans deux Passages | `--date` avec moins de deux Passages | message clair, code 2 | — |

</intent-contract>

## Code Map

- `tests/unit/chaine/test_rejeu.py:89-182` -- `_differences`, `_differences_cles`, `_cellules`, `_textes_slides`, `_comparer` : à déplacer dans l'outil, le test les importe.
- `src/usine/contrats/passage.py:175-210` -- `FICHIERS_PASSAGE`, `EXCLUSIONS_REJEU` (lecture seule).
- `outils/mesurer_nfr2.py` -- mesure synthétique NFR-2, inchangée ; `tests/unit/outils/test_mesurer_nfr2.py` modèle de test d'outil (pyproject : `outils` est un paquet racine pour mypy et import-linter).
- `README.md:12-35` -- section « Performance (NFR-2) » périmée (bouchons).
- `tests/unit/domaine/meteo/test_reconciliation.py` -- réconciliation à 100 % (FR-13).
- `evaluation/zenodo/RAPPORT.md:21-26` -- chiffres SM-10.
- `_bmad-output/implementation-artifacts/spec-5-6-recette-du-rapport-sur-donnees-completes.md` (Résultats réels) -- Passage composite `20261012T222702Z-ec5fab`, premier terme du Rejeu réel.

## Tasks & Acceptance

**Execution:**
- `outils/verifier_rejeu.py` -- créer : fonctions de comparaison déplacées depuis le test, `differences(premier, second, date_arrete) -> set[tuple[str, str]]`, `hors_exclusions(...)`, CLI `uv run python outils/verifier_rejeu.py (<passage_1> <passage_2> | --date AAAA-MM-JJ [--racine .])` qui compare les deux derniers Passages de la date et sort 0/1/2 selon la matrice.
- `tests/unit/chaine/test_rejeu.py` -- importer la comparaison depuis l'outil, assertions inchangées.
- `tests/unit/outils/test_verifier_rejeu.py` -- couvrir les quatre lignes de la matrice sur des Passages réduits fabriqués.
- `README.md` -- remplacer la section NFR-2 par la mesure synthétique du jour et la mesure réelle sur `DEMO`.
- `docs/journal-jalon-m3.md` -- créer le journal de fin de jalon : critères M3 et preuves, avance de l'Epic 6 (6.1 à 6.7 avant la porte, décision de l'orchestrateur, sans dépendance aux sorties du Palier 1), arbitrages SM-10 et AD-16, CI vérifiée par l'orchestrateur.
- Dépôt principal -- `uv run usine rapport --date-arrete 2026-10-09` (Palier 1, composite), puis `verifier_rejeu --date 2026-10-09` ; `pytest tests/unit/domaine/meteo/test_reconciliation.py` ; `outils/mesurer_nfr2.py` ; résultats consignés ci-dessous et au journal M3.

**Acceptance Criteria:**
- Given le poste de l'auteur décrit dans le README et la volumétrie de FR-2, when l'auteur mesure `usine rapport` en Palier 1 (synthétique et `DEMO` avec extraction incrémentale), then la durée est inférieure à 5 minutes et la mesure est consignée dans le README.
- Given deux Passages composites réels du 2026-10-09, when `verifier_rejeu` les compare, then seuls des champs de `EXCLUSIONS_REJEU` diffèrent (code 0).
- Given la porte M3, when l'auteur relit `docs/journal-jalon-m3.md`, then il y trouve la réconciliation à 100 %, le Rejeu idempotent, la mesure NFR-2, l'avance de l'Epic 6 et les arbitrages SM-10 et AD-16 en attente.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass
- verdicts: 6 findings — high 0, medium 0, low 6, false 0, maybe-false 0
- findings:
  - `[low]` `[patch]` `--date` peut retenir un dossier sans `manifeste.json` (traceback) — patch : `derniers_passages` ne retient que les dossiers qui ont un manifeste ; test `test_date_ignore_un_dossier_sans_manifeste`.
  - `[low]` `[patch]` Deux Passages explicites de Dates d'arrêté différentes donnent de fausses différences `<fichier>` — patch : code 2 et message si les dates diffèrent ; test `test_dates_d_arrete_differentes`.
  - `[low]` `[reject]` Deux Passages lancés dans la même seconde seraient mal ordonnés — improbable (un Passage dure 9 s, verrou de la Chaîne) et le correctif ajoute une lecture de manifeste par dossier.
  - `[low]` `[reject]` Libellé dupliqué dans une slide : `ValueError` non rattrapée — échec bruyant avec code non nul, comme l'assertion d'origine du test ; aucun rendu actuel ne le déclenche.
  - `[low]` `[reject]` `python -OO` vide `__doc__` — mode jamais utilisé, l'outil se lance par `uv run python`.
  - `[low]` `[reject]` Manifeste malformé : traceback au lieu du code 2 — échec bruyant sur un état que la Chaîne ne publie pas (écriture validée par contrat).

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q` -- expected: verts.
- CI GitHub -- vérifiée par l'orchestrateur sur le SHA intégré à `main` après push.

## Résultats réels

Dépôt principal, 2026-10-13, Palier 1, Jira en lecture seule.

- **Rapport composite** : `uv run usine rapport --date-arrete 2026-10-09`, exécuté deux fois. Passages `20261012T223154Z-8a7542` et `20261012T223234Z-d4f585`, source `composite`, 3 547 tickets, `nb_alignements` 0. Commande de bout en bout : 9,9 s puis 9,3 s. Extraction incrémentale : 2,3 s puis 1,5 s.
- **Rejeu** : `verifier_rejeu --date 2026-10-09` compare `8a7542` et `d4f585`. Code 0, 16 différences, toutes exclues. Le premier essai comparait `ec5fab` (Story 5.6) et `8a7542` : code 1 sur `manifeste : nb_alignements` (20 014 contre 0). Ce champ compte les alignements nouvellement persistés et n'est pas exclu. L'écart est consigné au journal M3 comme arbitrage ; `EXCLUSIONS_REJEU` n'a pas été modifié.
- **Réconciliation** : `pytest tests/unit/domaine/meteo/test_reconciliation.py`, 9 tests passés.
- **NFR-2 synthétique** : `outils/mesurer_nfr2.py`, 5 036 tickets, 63 817 événements, Chaîne en 5,39 s (`meteo` 3,06 s).
- **Contrôles du worktree** : ruff, format, mypy (307 fichiers), lint-imports (14 contrats) et pytest (2 541 passés, 1 sauté) sont verts.

## Auto Run Result

- **Résumé** : porte Palier 1 (M3). Mesure NFR-2 refaite avec toutes les étapes déterministes réelles (5,39 s en synthétique, 9,3 s sur `DEMO` en extraction incrémentale) ; comparaison du Rejeu extraite dans `outils/verifier_rejeu.py` et exécutée sur deux Passages composites réels (code 0, 16 différences toutes exclues) ; réconciliation à 100 % (9 tests) ; journal de fin de jalon `docs/journal-jalon-m3.md`.
- **Fichiers** : `outils/verifier_rejeu.py` (nouveau, comparaison et CLI) ; `tests/unit/chaine/test_rejeu.py` (importe la comparaison, assertions inchangées) ; `tests/unit/outils/test_verifier_rejeu.py` (nouveau, matrice + 2 cas de revue) ; `README.md` (section NFR-2) ; `docs/journal-jalon-m3.md` (nouveau).
- **Revue** (mode économique, Edge Case Hunter seul) : 2 low patchés, 4 low rejetés (raisons au journal de tri) ; aucun différé. Revue de suivi : `false` (aucun high, aucun medium patché).
- **Vérification** : ruff, format, mypy, lint-imports (14 contrats) verts ; `pytest -q` 2543 passés, 1 sauté, 39 désélectionnés ; Rejeu réel relancé après patch : code 0. CI GitHub : vérifiée par l'orchestrateur sur le SHA intégré à `main` (cette story ne pousse pas).
- **Risques résiduels** : constat `nb_alignements` (le Rejeu échoue entre le premier Passage après réinjection et le suivant) consigné comme arbitrage pour Anaël ; fichiers hors lane 5 (`outils/`, `docs/`, `README.md`) : le contrôle de chemins de la CI ne tourne que sur les branches `lane/*`, non poussées.
