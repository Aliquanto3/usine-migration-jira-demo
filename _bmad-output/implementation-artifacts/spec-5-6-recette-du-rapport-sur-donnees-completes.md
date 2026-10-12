---
title: 'Story 5.6 : Recette du Rapport sur données complètes'
type: 'feature'
created: '2026-10-13'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-5-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/sprint-change-proposal-2026-10-12-contrats-1-2.md'
warnings: []
deferred: []
baseline_revision: 'b02d749f3c5b1a18b08323ef36d896271783c1fb'
---

<intent-contract>

## Intent

**Problem:** le Rapport n'a été vérifié que sur le Programme réduit (2 Entités). Rien ne prouve qu'il tient sur le Journal complet (10 Entités, graine 42) avec A et B rouges, C orange et les Prévisions des Scénarios, ni sur la Source composite du projet `DEMO` réinjecté. La copie du Mode repli (`demo/repli/passage/`) date d'avant le recalage des contrats 1.2. Enfin, les contrats 1.2 ont fait perdre la couverture de « ↗ aggravation » (Carte météo) et de « aucun Brouillon de commentaire » (slide d'Entité en Palier 2).

**Approach:** un test `lent` lance `lancer_rapport` en Palier 1 sur le Journal complet généré (graine 42, `config/programme.yaml` livré) et vérifie couleurs, slides et Prévisions. Deux tests rapides sur des Passages réduits fabriqués reprennent la couverture perdue. La copie du Mode repli est régénérée par la procédure documentée, et les tests qui la lisent sont réalignés. La recette réelle sur `DEMO` (Source composite, lecture seule) est exécutée depuis le dépôt principal et consignée.

## Boundaries & Constraints

**Always:** Palier 1 (aucun appel LLM réel, aucune clé LLM en jeu) ; Jira en lecture seule ; `contrats/` et `ports/` intacts ; tests par défaut sans réseau ; régénération du repli avec `USINE_MODE_REPLI=1`, graine 42, génération le 2026-10-12, Date d'arrêté 2026-10-09 ; résultats réels (Passage, comptes, couleurs, durée) consignés ici et au journal du run.

**Never:** écrire dans Jira ; lire, afficher ou copier `.env` ; régler le générateur ou la Grille pour faire passer la recette ; versionner `donnees/journal.jsonl` ou un Passage composite.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Journal complet | Journal graine 42, Palier 1, 2026-10-09 | A, B rouges ; C orange ; slides 3 à 5 = `ENT-A — Rouge`, `ENT-B — Rouge`, `ENT-C — Orange` ; Prévision A `sortie_projetee`, B `pas_de_sortie_projetee` ; Risque d'entrée en rouge sur C | — |
| Aggravation | Météo d'une Entité jaune à J-5, rouge à J | Carte météo : `↗ aggravation` | — |
| Sans Brouillon | Palier 2, deux Entités rouge/orange, Explication avec Brouillon pour une seule | l'autre slide affiche `aucun Brouillon de commentaire` | — |
| Repli régénéré | `demo/repli/passage/` nouveau | A, B rouges, C orange ; `passage_id` des fichiers = celui du manifeste ; liens inactifs | — |
| Composite `DEMO` | dépôt principal, `config/jira.yaml`, secrets de lecture | Passage publié, source `composite`, liens `…/browse/DEMO-n` | échec Jira : Passage non publié, consigné |

</intent-contract>

## Code Map

- Emplacement : tout le code, les tests et la copie du repli se font dans le worktree `C:/Users/Utilisateur/Documents/GitHub/usine-lanes/lane-5-rapport` (branche `lane/5-rapport`), sans commit. La régénération du repli se fait dans un répertoire temporaire (copie de `config/`, `gabarits/`, `donnees/corpus/`), avec `uv run --project <worktree>`. La dernière tâche (« Dépôt principal ») est réservée à l'orchestrateur, après intégration : ne pas l'exécuter.
- `tests/unit/chaine/environnement.py` -- `preparer_racine` (Programme réduit, `generer_journal` graine 42), `horloge_figee`, `DATE_ARRETE`, `RACINE_DEPOT` : à réutiliser, avec un paramètre pour garder `config/programme.yaml` livré.
- `tests/unit/rendu/conftest.py` -- `passage_jaune_rouge` (Passage réduit à `meteo.json`), `_ecrire_json`, `CONTEXTE_FICTIF`, `completer_palier_2` : modèles des scénarios dédiés.
- `tests/unit/rendu/test_powerpoint.py:221` (`test_carte_meteo`, flèches) et `:386` (`test_palier_2_brouillons`) -- couverture perdue (diff `a663bf3`) ; `_lire`, `GABARIT`.
- `src/usine/consultation/passage.py:307` -- `evolution_meteo` lit J-5 dans l'historique de `meteo.json`.
- `src/usine/ui/cli.py:27` -- docstring de `REPERTOIRE_REPLI` : procédure de régénération et `passage_id` actuel.
- `tests/unit/ui/test_repli.py:11` -- `PASSAGE_ID` de la copie.
- `demo/repli/passage/` -- copie versionnée à remplacer.
- `pyproject.toml:65` -- marqueur `lent` exclu par défaut.

## Tasks & Acceptance

**Execution:**
- `tests/unit/chaine/environnement.py` -- `preparer_racine` accepte `programme_complet: bool = False` (garde `config/programme.yaml` livré) -- recette sur la volumétrie cible.
- `tests/unit/chaine/test_recette_complete.py` -- créer, marqué `lent` : Passage Palier 1 sur le Journal complet, assertions de la ligne « Journal complet » de la matrice (Consultation et PowerPoint publiés, 9 onglets Excel) -- AC 1.
- `tests/unit/rendu/test_powerpoint.py` -- ajouter les scénarios « Aggravation » et « Sans Brouillon » sur Passages réduits fabriqués (`meteo.json` à J-5 et J ; `llm/explications.json`) -- couverture perdue en contrats 1.2.
- `demo/repli/passage/` -- remplacer par le Passage régénéré -- AC 3 (C10, AD-24).
- `src/usine/ui/cli.py`, `tests/unit/ui/test_repli.py` -- nouveau `passage_id` ; `test_repli` vérifie aussi Prévision A, B et Risque C.
- Dépôt principal, après intégration -- `uv run usine rapport --date-arrete 2026-10-09` sur `DEMO`, résultats consignés ci-dessous -- AC 2.

**Acceptance Criteria:**
- Given le Journal généré à la volumétrie cible, when l'auteur lance `usine rapport` en Palier 1, then le Rapport montre A et B rouges, C orange, une slide pour chacune et les Prévisions attendues.
- Given la Source composite sur le projet `DEMO`, when l'auteur lance `usine rapport`, then le Passage est publié et les liens des tickets ouvrent les tickets de `DEMO`.
- Given le Passage recalé de la volumétrie cible, when l'auteur régénère `demo/repli/passage/`, then le Mode repli montre A et B rouges et C orange, comme en direct.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass
- verdicts: 3 findings — high 0, medium 0, low 2, false 0, maybe-false 0 (+1 rejeté)
- findings:
  - `[low]` `[patch]` La recette vérifie les Prévisions par la Consultation seulement, pas dans le PowerPoint — patch : la zone « Prévision » des slides ENT-A, ENT-B et ENT-C est comparée à `texte_prevision` et doit être non vide.
  - `[low]` `[patch]` Seul le nombre d'onglets Excel est vérifié — patch : liste exacte et ordonnée des 9 onglets.
  - `[low]` `[reject]` Le spec 7.6 cite encore l'ancien `passage_id` — historique d'une story close ; la référence vivante (docstring de `REPERTOIRE_REPLI`, `test_repli`) porte le nouvel identifiant, que la 7.11 lira.

## Verification

**Commands:**
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports` -- expected: aucun écart.
- `uv run pytest -q` puis `uv run pytest -q -m lent tests/unit/chaine/test_recette_complete.py` -- expected: verts.

## Auto Run Result

- **Résumé** : recette du Rapport sur le Journal complet (test `lent`), deux scénarios rapides qui reprennent la couverture perdue en contrats 1.2 (« ↗ aggravation », « aucun Brouillon de commentaire »), copie du Mode repli régénérée sur le Journal recalé, recette réelle sur `DEMO` en Source composite.
- **Fichiers** : `tests/unit/chaine/environnement.py` (`programme_complet`) ; `tests/unit/chaine/test_recette_complete.py` (nouveau, `lent`) ; `tests/unit/rendu/test_powerpoint.py` (2 scénarios) ; `demo/repli/passage/` (régénéré) ; `src/usine/ui/cli.py` (docstring, nouveau `passage_id`) ; `tests/unit/ui/test_repli.py` (`PASSAGE_ID`, Prévisions et Risque attendus).
- **Revue** (mode économique, Edge Case Hunter seul) : 2 low patchés, 1 low rejeté ; aucun différé. Revue de suivi : `false` (aucun high, aucun medium patché).
- **Vérification** : ruff, format, mypy, lint-imports (14 contrats) verts ; `pytest -q` 2535 passés, 1 sauté, 39 désélectionnés ; recette `lent` verte (8 s).
- **Risques résiduels** : fichiers hors lane (`ui/cli.py`, `tests/unit/ui/test_repli.py`) touchés par nécessité ; la Story 7.11 doit enregistrer ses réponses sous le nouveau `passage_id`.

## Résultats réels

**Journal complet (test `lent`, worktree `lane/5-rapport`, 2026-10-13)** : `test_recette_complete.py` vert en 6 à 7 s (Palier 1, 10 Entités). A et B rouges, C orange ; slides 3 à 5 = `ENT-A — Rouge`, `ENT-B — Rouge`, `ENT-C — Orange` ; Prévision A `sortie_projetee`, B `pas_de_sortie_projetee` ; Risque d'entrée en rouge sur C ; Excel à 9 onglets.

**Repli régénéré (2026-10-13)** : répertoire temporaire (copie de `config/`, `gabarits/`, `donnees/corpus/`), `USINE_MODE_REPLI=1`, `uv run --project <worktree> usine donnees generer --graine 42 --date-generation 2026-10-12` (42 450 événements, 919 identifiants fictifs), puis `usine rapport --date-arrete 2026-10-09` en 7,5 s. Passage `20261012T221158Z-96c621`, source `journal`, Palier 1, 3 547 tickets, `contrats_version` 1.6.0, `version_grille` `c344967e71de`. Météo : A, B rouges ; C orange ; D vert ; E à J jaunes. Prévisions : A `sortie_projetee`, B `pas_de_sortie_projetee` ; Risque C sur IND-4. Liens inactifs (`url_ticket` = `None`), `passage_id` des fichiers = celui du manifeste (`test_repli`).

**Composite `DEMO`** : non exécuté ici, réservé à l'orchestrateur depuis le dépôt principal après intégration.
