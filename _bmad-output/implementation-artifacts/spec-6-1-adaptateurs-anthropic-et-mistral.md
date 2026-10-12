---
title: 'Story 6.1 : adaptateurs Anthropic et Mistral'
type: 'feature'
created: '2026-10-12'
status: 'done'
baseline_revision: 'bdfe6b28ad13c248f7acd58bb89f7d4fc8860abc'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md'
warnings: []
deferred:
  - 'composition : fermer() de l adaptateur LLM en fin de construire_rapport (low, Story 6.3)'
  - 'température décidée par fournisseur et non par modèle ; ConfigLLM.temperature non lu (low, Story 6.3)'
---

<intent-contract>

## Intent

**Problem:** Le port `FournisseurLLM` n'a qu'une doublure : aucun appel réel n'est possible, et le choix du fournisseur n'est pas configurable (Story 6.1 ; FR-30, NFR-7, NFR-9 ; AD-12, AD-13, AD-19, AD-20).

**Approach:** `adaptateurs/llm` implémente le port sur Pydantic AI pour Anthropic et Mistral (`FournisseurPydanticAI`), avec reprise sur 429, espacement par modèle et registre des quotas et des prix. La composition construit l'adaptateur depuis `config/llm.yaml` et la clé du fournisseur. Les tests passent par un faux transport HTTP (réponses au format des API publiques), jamais par le réseau.

## Boundaries & Constraints

**Always:** `pydantic_ai`, `anthropic`, `mistralai` importés seulement dans `usine.adaptateurs.llm` (contrat import-linter dédié). Reprises internes des SDK coupées (`max_retries=0` côté Anthropic) : seule la boucle de l'adaptateur reprend. Aucun message d'erreur ne recopie la clé ni le corps de réponse.

**Never:** modifier `contrats/` ou `ports/` ; toucher la Pseudonymisation (Story 6.2, lane parallèle) ; appeler une vraie API dans les tests.

**Modèle par défaut :** `claude-sonnet-5-5` (consigne de l'orchestrateur ; l'architecture n'impose aucun modèle, seulement « Anthropic d'abord, Mistral ensuite », H-23). Mistral : `mistral-large-latest` dans les tests et le registre.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Choix par configuration | `config/llm.yaml` `fournisseur: anthropic` ou `mistral` + clé | adaptateur correspondant, `version_modele = fournisseur:modele` | clé absente → `UsineErreur` nommant la variable |
| Structure | `generer_structure` | requête avec le seul outil de sortie `reponse` (Tool Output) | N/A |
| Agent | `executer_agent` | requêtes avec les seuls outils reçus, `output_type=str` | outil inconnu → `UsineErreur`, aucun outil exécuté |
| 429 | deux 429 (`Retry-After: 3`, puis sans) puis succès | attentes 3 s puis 6 s, succès | au-delà de `tentatives_max` → `UsineErreur` |
| Autre erreur HTTP | 401 | `UsineErreur` sans reprise ni clé | N/A |
| Fournisseur ou modèle inconnu | `openai`, modèle hors registre | `UsineErreur` | N/A |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/llm/fournisseur.py` -- `FournisseurPydanticAI`, `construire_fournisseur_llm(config, cle_api, client_http, attendre, horloge)`, conversions `MessageAgent` ↔ messages Pydantic AI, boucle de reprise.
- `src/usine/adaptateurs/llm/registre.py` -- `REGISTRE`, `TarifModele`, `tarif`, `cout_estime_eur` (prix en euros, quotas gratuits Mistral).
- `src/usine/composition.py` -- `construire_fournisseur(racine)` (import différé) ; `construire_rapport` construit le fournisseur en Palier 2 si `config/llm.yaml` existe et qu'aucun n'est injecté.
- `config/llm.yaml` -- Anthropic, `claude-sonnet-5-5`.
- `pyproject.toml` -- contrat import-linter « pydantic_ai, anthropic, mistralai : adaptateurs/llm seulement ».
- `tests/doublures/transport_llm.py` -- `TransportScripte` et réponses enregistrées Anthropic/Mistral.

## Tasks & Acceptance

**Execution:**
- [x] `src/usine/adaptateurs/llm/` -- adaptateur, registre, export.
- [x] `src/usine/composition.py`, `config/llm.yaml` -- construction par configuration.
- [x] `pyproject.toml`, `tests/depot/test_import_linter.py` -- contrat d'isolation et sa preuve de rupture.
- [x] `tests/contrat/fournisseur_llm/fabriques.py` -- Anthropic et Mistral sur enregistrements.
- [x] `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/unit/test_composition_llm.py`, `tests/unit/chaine/test_execution.py`, `tests/unit/contrats/test_config.py` -- matrice I/O.

**Acceptance Criteria:**
- Given le worktree, when `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `pytest -q`, then tout passe.

## Auto Run Result

Implémentation livrée. Revue Edge Case Hunter (une passe, aucun high) : 7 constats.
- Corrigés : reprise 429 et espacement déplacés au niveau de chaque requête modèle (`_ModeleRepris`), les outils ne sont plus rejoués ; `RetryPromptPart` traduit en message « outil » ; exception d'outil traduite en `UsineErreur` ; message « assistant » vide refusé ; adaptateur fermé → `UsineErreur`. Tests de non-régression ajoutés.
- Reportés (low, Story 6.3) : fermeture de l'adaptateur par la composition ; température décidée par modèle et lecture de `ConfigLLM.temperature`.
Contrôles verts : ruff, ruff format, mypy, lint-imports (14 contrats), pytest.
