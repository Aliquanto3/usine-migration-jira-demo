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
deferred: []
---
## Intent

**Problem:** Si la banque refuse tout LLM distant, la couche LLM doit tourner avec un modèle exécuté sur le poste (FR-37).

**Approach:** Un troisième fournisseur, `local`, derrière le même port `FournisseurLLM` : `llama-server` (tag b11552, lancé avec `--jinja`) sert `/v1/chat/completions` ; l'adaptateur réutilise le client Mistral déjà en dépendance, pointé sur le serveur local. Aucune dépendance ajoutée, `contrats/` et `ports/` intacts.

## Boundaries & Constraints

**Always:** `generer_structure` en Tool Output seul, `executer_agent` avec les seuls outils reçus : jamais de schéma et d'outils dans un même appel (inchangé, `FournisseurPydanticAI`). `fournisseur: local` : pas de clé, coût 0, tout nom de modèle admis (`local:<modele>`).

**Never:** appel à un `llama-server` réel dans les tests ; modifier `contrats/` ou `ports/`.

## Critères d'acceptation

- [x] `config/llm.yaml` peut désigner `fournisseur: local` (documenté dans le fichier) ; adresse de `llama-server` par `USINE_LLAMA_SERVER_URL` (défaut `http://127.0.0.1:8080`).
- [x] L'adaptateur `local` passe la suite de contrat `FournisseurLLM` (fabrique `local`, réponses au format `llama-server` sur faux transport), sans combiner schéma et outils.
- [ ] Suites d'évaluation de l'Explication et de la classification relancées sur le modèle local, résultats publiés : voir Reports.

## Tâches

- [x] `adaptateurs/llm/fournisseur.py` : fournisseur `local`, `URL_LLAMA_SERVER`, clé non exigée.
- [x] `adaptateurs/llm/registre.py` : `TARIF_LOCAL` (0 €, espacement 0,1 s) pour `local:<modele>`.
- [x] `composition.py` : `_url_serveur_local()` transmise aux deux constructions de fournisseur.
- [x] Doublures : `llama_outil`/`llama_texte`, fabrique `local` de la suite de contrat.
- [x] Tests unitaires (URL, absence de clé, coût nul, agent) et de composition.

## Fichiers modifiés

`config/llm.yaml`, `src/usine/adaptateurs/llm/{__init__,fournisseur,registre}.py`, `src/usine/composition.py`, `tests/doublures/transport_llm.py`, `tests/contrat/fournisseur_llm/fabriques.py`, `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/unit/test_composition_llm.py`.

## Reports

- **Évaluations sur modèle local** (Explication, classification) : exigent un `llama-server` réel et un GGUF quantifié, exclus de ce run. À lancer sur le poste : démarrer `llama-server --jinja -m <modele.gguf>`, `fournisseur: local` dans `config/llm.yaml`, puis `uv run python -m evals.explication executer --reel` et `uv run python -m evals.classification ... --reel`, et publier les résultats dans `evals/*/resultats/`.
- Le client Mistral parle au serveur local au format Chat Completions ; à confirmer sur le serveur réel (tool_choice requis en Tool Output).
- `modeles_par_tache` de `config/llm.yaml` : à aligner sur le modèle local lors du basculement.

## Résultats des contrôles

ruff check, ruff format --check, mypy, lint-imports (15 contrats) verts ; pytest : 2836 passés, 1 ignoré, 39 désélectionnés.
