---
title: 'Story 6.12 : [BONUS] Mode LLM local'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff5453a900b4a4180082493318d46fde9e167'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md'
warnings: []
deferred:
  - 'relance des suites d evaluation (explication, classification) sur un vrai modèle local, résultats publiés (seconde partie des critères de la Story 6.12 ; nécessite un llama-server b11552 et un GGUF tenant en 8 Go de VRAM)'
  - 'client openai dédié : le Chat Completions de llama-server est lu par le client Mistral (aucune dépendance ajoutée) ; à remplacer par OpenAIChatModel si un champ propre à llama-server n est pas toléré lors de la relance réelle (low)'
  - 'URL du serveur local par variable USINE_LLM_LOCAL_URL faute de champ dans ConfigLLM (contrats gelés) ; un champ additif url_serveur serait plus lisible (low)'
---

<intent-contract>

## Intent

**Problem:** Si la banque refuse tout LLM distant, la couche LLM n'a aucun fournisseur local (Story 6.12 ; FR-37 ; AD-13, AD-20).

**Approach:** `config/llm.yaml` accepte `fournisseur: local` : l'adaptateur existant `FournisseurPydanticAI` vise un `llama-server` (tag b11552, API compatible OpenAI) sans clé, à `http://127.0.0.1:8080` ou `USINE_LLM_LOCAL_URL`. Tout modèle `local:<modele>` a un tarif nul dans le registre. `generer_structure` (outil de sortie seul) et `executer_agent` (outils reçus seuls) ne combinent jamais schéma et outils. Transport simulé dans les tests, aucun `llama-server` requis.

## Boundaries & Constraints

**Always:** aucune clé ni appel réseau pour `local` ; `contrats/` et `ports/` inchangés ; pas de nouvelle dépendance.

**Never:** combiner schéma et outils dans une requête ; lancer les suites d'évaluation sur un vrai modèle dans ce lot.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Choix local | `fournisseur: local`, clé vide | adaptateur, `version_modele = local:<modele>` | N/A |
| URL | défaut / `USINE_LLM_LOCAL_URL` / paramètre | requêtes sur `<url>/v1/chat/completions` | N/A |
| Structure puis Agent | une requête chacun | outil `reponse` seul, puis outils reçus seuls | outil inconnu → `UsineErreur` |
| Coût | `local:<gguf>` | 0 €, quota local large | `locale:x` → `UsineErreur` (registre) |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/llm/fournisseur.py` -- `local` dans `FOURNISSEURS`, `URL_LOCAL_DEFAUT`, `VARIABLE_URL_LOCAL`, branche de `construire_fournisseur_llm` (paramètre `url_serveur`).
- `src/usine/adaptateurs/llm/registre.py` -- `LOCAL`, repli de `tarif` pour `local:*`.
- `config/llm.yaml` -- documentation du fournisseur `local`.
- `tests/contrat/fournisseur_llm/fabriques.py`, `tests/doublures/transport_llm.py`, `tests/unit/adaptateurs/llm/test_fournisseur.py` -- cas `local` de la suite de contrat et tests dédiés.

## Tasks & Acceptance

- [x] Adaptateur local, tarif nul, configuration documentée.
- [x] Suite de contrat `FournisseurLLM` paramétrée avec `local` ; tests d'URL, de non-combinaison et de tarif.
- [ ] Reporté : suites d'évaluation sur un modèle local.

**Acceptance Criteria:**
- Given `config/llm.yaml` désignant `local`, when la suite de contrat s'exécute sur le faux transport, then elle passe, et aucune requête ne déclare à la fois le schéma de sortie et des outils.
- Given la CI, when `uv run pytest -q` s'exécute, then aucun réseau n'est utilisé.

## Verification

- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q` -- expected: tout vert.
- Report, avec `llama-server` b11552 lancé (`llama-server -m <modele.gguf> --jinja --port 8080`), `fournisseur: local` et `modele` posés dans `config/llm.yaml` :
  `uv run python -m evals.explication executer --reel` puis `uv run python -m evals.classification executer --reel`, résultats à publier dans `evals/*/resultats` et `historique.jsonl`.
