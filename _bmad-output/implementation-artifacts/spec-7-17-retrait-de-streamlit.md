---
title: "Story 7.17 : Retrait de Streamlit"
type: 'refactor'
created: '2026-10-18'
status: 'done'
baseline_revision: '30a5f05'
review_loop_iteration: 0
followup_review_recommended: false
context: ['_bmad-output/implementation-artifacts/epic-7-context.md']
warnings: []
deferred: ['pyarrow reste en 25.0.1 : plus aucune contrainte `< 26` ne le bloque, la montée vers 26 est hors du lot (à étudier avec les tests de Parquet)', 'GIF du README (`docs/media/demo-ui.gif`) : conservé, légende rendue neutre ; réenregistrement sur la nouvelle UI en Story 7.12']
---

<intent-contract>

## Intent

**Problem:** l'UI Streamlit (`ui/app.py`, option `--streamlit`) est remplacée par l'UI FastAPI (Stories 7.13 à 7.16) mais reste dans le code, les dépendances, les tests et les documents.

**Approach:** suppression de `app.py`, de l'option et du code mort qui ne servait que Streamlit ; `streamlit` retiré de `pyproject.toml`, du contrat import-linter, de `uv.lock` et de `tests/depot/` ; tests de pilotage Streamlit remplacés par un bout en bout `TestClient` ; documents alignés sur le § 4.5 du SCP du 2026-10-17.

## Boundaries & Constraints

**Always:** `uv lock` sans `--upgrade` (aucune version ne monte) ; `starlette` 1.7.0 et `pyarrow` 25.0.1 inchangés ; les constantes de texte partagées vivent dans `ui/textes.py`.

**Never:** modifier `src/usine/contrats/` ou `src/usine/ports/` ; toucher `sprint-status.yaml`, le journal ou la version du projet.

## Code Map

- `src/usine/ui/app.py` -- supprimé (687 lignes) ; `ui/cli.py` -- `--streamlit`, `commande_streamlit`, `CHEMIN_APP` retirés.
- `ui/carte.py`, `detail.py`, `avant_apres.py`, `liens.py`, `progression.py`, `agent.py` -- sorties Markdown mortes retirées (`tableau_markdown`, `lien_ticket`, `echapper_markdown`, `lignes_carte`, `lignes_regles`, `lignes_kpi`, `texte_prevision`, `texte_risques`, `texte_explication`, `tableau_avant_apres`, `etat_des_etapes`, `ligne_suivi`, libellés de boutons, `texte_outils`…). `vue_ticket` reste.
- `ui/textes.py` -- déjà source des constantes (`INTERVALLE_SONDAGE`, `LIGNES_ERREUR_MAX`, `BANDEAU_REPLI`…) ; docstring mise à jour. Le doublon `_moteur_indisponible` disparaît avec `app.py` (`pseudonymisation.moteur_indisponible` seul).
- `pyproject.toml`, `uv.lock`, `tests/depot/*`, spine -- voir Design Notes.
- `docs/fiche-outillage.md`, `demo/script-demo.md`, `SPEC-usine-migration-jira-demo.md`, `docs/QUESTIONS.md` (H-28), `docs/tests-manuels.md`, `README.md`, `tests/unit/docs/test_fiche_outillage.py`.
- `tests/unit/ui/test_bout_en_bout.py` -- réécrit ; `test_app.py` et `test_app_agent.py` supprimés.

## Tasks & Acceptance

**Acceptance Criteria:** ceux de la story 7.17 (epics.md). `git grep -i streamlit` ne renvoie plus que l'historique ci-dessous.

## Design Notes

**Dépendances.** Le lock perd 15 paquets, aucune version ne bouge : streamlit, altair, attrs, httptools, itsdangerous, jsonschema, jsonschema-specifications, pandas, pydeck, python-multipart, referencing, rpds-py, toml, watchdog, websockets. `tzdata` reste au lock mais n'était tiré que par pandas (Windows) et `ZoneInfo("Europe/Paris")` (`contrats/calendrier.py`) en dépend : il devient dépendance directe `tzdata==2026.5` (même version, classé dans `tests/depot` sans module, ligne ajoutée au spine). `uv.lock` : au final 2 lignes ajoutées (la dépendance directe), 264 retirées.

**Tests retirés.** Les tests `AppTest` (`test_app.py`, `test_app_agent.py`, `test_chaine::test_constantes_communes_avec_streamlit`, 3 tests de `--streamlit`) et les tests des sorties Markdown supprimées dans `test_carte`, `test_detail`, `test_liens`, `test_avant_apres`. La parité fonctionnelle reste couverte par les tests `TestClient` de 7.13 à 7.16 (`test_serveur`, `test_chaine`, `test_ecrans_web`, `test_vues_ecrans`). `test_progression` garde le suivi par étape et l'étape en échec (réécrits sans `ligne_suivi`). Nouveau : bout en bout réel (`POST /api/chaine`, `usine rapport`, carte, détail, livrable) et parcours Mode repli (bascule, carte, détail, livrable).

**Fiche outillage.** Le texte exact du SCP allonge la fiche à 741 mots : `MOTS_MAX` passe de 700 à 750.

**Reste de `git grep -i streamlit` (historique légitime).** `_bmad-output/planning-artifacts/` : SCP, `epics.md`, spine (carte E0-8 « remplacé par AD-25 », décision UX du 17/10), recherches, revues de versions, UX (`DESIGN.md`, `EXPERIENCE.md`, rubriques), PRD addendum, `.memlog.md` ; `_bmad-output/implementation-artifacts/` : specs terminées 0-1, 0-8, 7-1 à 7-16, 8-1, contextes d'epic, rétro E0, journal, `sprint-status.yaml`. Dans le code : aucune occurrence. `README.md`, `docs/`, `demo/`, `SPEC-…md`, `src/`, `pyproject.toml`, `uv.lock` : zéro occurrence.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q --tb=short` -- 2 875 passés, 1 ignoré.
- `uv run usine ui --help` -- ne cite plus `--streamlit`.
- `verif_nav.sh <worktree> 8765 / /entites/ENT-A /chaine /agent /avant-apres /outillage` et `verif_nav_pseudo.sh` (`/pseudonymisation?ticket=DEMO-17`) -- sortie 0.

## Revue

Revue unique (Opus) du 2026-10-18 sur `30a5f05..a8c3175`, avec la liste du second avis (Haiku).

- medium · second avis 1 · corrigé · réel : plus aucun test des règles du détail. Rétablis en version structurée contre `section_prevision`, `section_risque`, `section_explication` : pas de sortie projetée, règle non projetable (IND-2), narration conforme ou corrigée qui remplace la Prévision, repli sur la Prévision brute (narration rejetée, non contrôlée, autre Entité), Explication rejetée sans citations, citation absente du texte, Mode repli, Palier 1 et colonne « Valeur projetée » (absente, présente, mixte).
- medium · second avis 2 · corrigé · réel : `test_citations_bornees` contre `_morceaux` (DEMO-1 non reconnu dans DEMO-12, XDEMO-1, DEMO-1-2).
- medium · second avis 3 · corrigé · réel : `CLE_*`, `libelles_ecrans` et `ouvrir_detail` n'avaient plus aucun appelant (`git grep`) ; supprimés de `navigation.py` avec leurs tests (l'ordre des écrans reste testé sur `Ecran`).
- medium · second avis 7 · corrigé · mesuré : 4,8 s en local, 60 s de délai max, écritures sous `tmp_path` (racine d'essai copiée, `chdir`), Palier 1 (`config/chaine.yaml`) donc aucun LLM, `JIRA_*` absent de la racine (pas de `.env`) et socket externe refusée dans les tests. Le sous-processus héritait de l'environnement du shell : le test retire désormais les variables Jira, LLM, Pseudonymisation, `USINE_RACINE` et Mode repli. Pas de marqueur `lent` (4,8 s, fixture déjà utilisée par la suite).
- low · second avis 4 · corrigé · `test_ui_sans_acces_interdit` rétablie dans `test_ecrans_web` (AD-11).
- low · second avis 5 · corrigé · `test_avant_apres_milliers_et_arrondi` : 240 min donne « 1 200 min », 12,34 s donne « 12,3 s » et « 61,7 s » via `/api/avant-apres`.
- low · second avis 6 · rejeté · `test_suivi_en_cours` et `test_suivi_derniers_evenements_et_incoherence` couvrent déjà `suivi_des_etapes` (réussie après en_cours, en_cours sans fin, EN_ATTENTE pour les suivantes, `list(suivis) == list(Etape)`) ; `etat_des_etapes` n'existe plus.
- low · second avis 8 · corrigé · `test_option_inconnue_refusee` (code 2) ne nomme plus le mot ; `git grep -il streamlit` hors `_bmad-output/` est vide.
- low · second avis 9 · rejeté · compte exact (741 mots, `test_tient_en_une_page` vert) ; `MOTS_MAX = 750` conservé.
- low · second avis 10 · corrigé · spec : 15 paquets retirés, `tzdata` conservé au lock et passé en direct.
- low · second avis 11 · corrigé · docstring de `ui/cli.py` : « il démarre le serveur web ».

Navigateur : `verif_nav.sh` sur `/`, `/entites/ENT-A`, `/chaine`, `/agent`, `/avant-apres`, `/outillage`, sortie 0.
