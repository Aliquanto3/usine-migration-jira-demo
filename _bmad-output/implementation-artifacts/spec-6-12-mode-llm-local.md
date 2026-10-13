---
title: "Story 6.12 : [BONUS] Mode LLM local"
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff54'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: ['relance réelle des évaluations SM-3 et SM-9 sur llama-server (aucun serveur ni GGUF à l''implémentation)']
---

<intent-contract>

## Intent

**Problem:** Si la banque refuse tout LLM distant, la couche LLM ne peut plus servir la démo (FR-37).

**Approach:** Un fournisseur `local` dans `adaptateurs/llm/`, qui parle à `llama-server` (tag b11552) par son API compatible OpenAI via Pydantic AI (`OpenAIChatModel`), derrière le même port `FournisseurLLM`. Choisi par `fournisseur: local` dans `config/llm.yaml`, sans clé d'API ni coût.

## Boundaries & Constraints

**Always:** schéma (Tool Output) et outils jamais combinés dans un même appel (inchangé, AD-13/AD-20) ; `openai` importé seulement dans `adaptateurs/llm/` (import-linter étendu) ; adresse du serveur par `LLM_LOCAL_URL`, défaut `http://127.0.0.1:8080/v1` ; tout `local:<nom>` admis au registre, coût nul.

**Never:** modifier `contrats/` ou `ports/` (aucun ajout nécessaire : l'adresse passe par une variable d'environnement, pas par `ConfigLLM`) ; appeler un vrai serveur ou LLM ; toucher la passerelle, le cache ou les contrôles.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Local nominal | `fournisseur: local`, clé absente | adaptateur `local:<modele>`, suite de contrat verte | — |
| Adresse | `LLM_LOCAL_URL` définie | requêtes vers cette adresse | — |
| Serveur éteint | connexion refusée | — | `UsineErreur` nommant `local:<modele>` |
| Nom vide | `local:` | — | `UsineErreur` registre |
| Fournisseur distant sans clé | `anthropic`, clé vide | — | inchangé : nomme la variable |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/llm/fournisseur.py` -- branche `local` (`openai.AsyncOpenAI` + `OpenAIChatModel`), clé non exigée.
- `src/usine/adaptateurs/llm/registre.py` -- `TARIF_LOCAL`, `tarif("local:...")`.
- `src/usine/composition.py` -- `_url_locale()` passé aux deux constructeurs.
- `pyproject.toml` -- extra `openai` de pydantic-ai-slim, contrat import-linter AD-12 étendu ; `uv.lock`.
- `docs/mode-llm-local.md`, `config/llm.yaml` -- procédure et commentaire.
- Tests : cas `local` ajouté à `tests/contrat/fournisseur_llm`, `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/unit/test_composition_llm.py`, doublure `transport_llm.py`.

## Tasks & Acceptance

**Acceptance Criteria:**
- Given `config/llm.yaml` avec `fournisseur: local`, when la composition construit le fournisseur, then l'adaptateur passe la suite de contrat `FournisseurLLM` (faux transport), sans combiner schéma et outils.
- Given `llama-server` démarré, when `python -m evals.explication executer --reel` et `python -m evals.classification executer --reel` s'exécutent, then les résultats se publient comme ceux du mode distant (procédure dans `docs/mode-llm-local.md`).

## Spec Change Log

## Design Notes

Le format des réponses de `llama-server` est celui des Chat Completions : les doublures Mistral servent de faux transport. L'API OpenAI envoie `max_completion_tokens` au lieu de `max_tokens` (llama.cpp accepte les deux). `--jinja` est requis côté serveur pour les appels d'outils.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -q`

## Auto Run Result

- **Résumé** : fournisseur `local` (`llama-server`) derrière `FournisseurLLM`, sans clé ni coût, adresse par `LLM_LOCAL_URL`.
- **Reporté** : relance réelle des suites d'évaluation (SM-3, SM-9) et publication des résultats, faute de serveur et de GGUF dans l'environnement ; commandes et protocole dans `docs/mode-llm-local.md`.
- **Écart** : dépendance `openai` ajoutée (extra de pydantic-ai-slim) ; `ConfigLLM` inchangé, donc aucune PR contrats.
