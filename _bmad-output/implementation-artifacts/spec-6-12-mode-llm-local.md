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
deferred: ['Relance réelle des suites d''évaluation (Explication, classification) sur llama-server et publication des résultats']
---
## Intent

**Problem:** Si la banque refuse tout LLM distant, la démo doit rester possible avec un modèle exécuté sur le poste (FR-37).

**Approach:** Troisième valeur de `fournisseur` dans `config/llm.yaml` : `local`, un `llama-server` (tag b11552, lancé avec `--jinja`) qui parle l'API Chat Completions d'OpenAI. L'adaptateur réutilise `FournisseurPydanticAI` avec `OpenAIChatModel` ; `generer_structure` (Tool Output, sans autre outil) et `executer_agent` (texte, outils reçus seulement) restent deux appels distincts : schéma et outils ne sont jamais combinés.

## Boundaries & Constraints

**Always:** aucune clé exigée pour `local` ; adresse de `llama-server` par `USINE_LLAMA_URL` (défaut `http://127.0.0.1:8080/v1`) ; `max_tokens` (pas `max_completion_tokens`) et pas de `strict` côté outils ; coût estimé nul, tout modèle `local:<nom>` admis ; serveur injoignable traduit en `UsineErreur` ; `openai` importé dans `adaptateurs/llm/` seulement (AD-12).

**Never:** modifier `contrats/` ou `ports/` (aucun ajout nécessaire : l'adresse passe par l'environnement) ; appel réseau ou `llama-server` réel dans les tests.

## Acceptance Criteria

- [x] `config/llm.yaml` avec `fournisseur: local` construit l'adaptateur sans clé (`construire_fournisseur`, `construire_fournisseurs_par_tache`).
- [x] L'adaptateur `local` passe la suite de contrat `FournisseurLLM` (`tests/contrat/fournisseur_llm`, cas `local` sur réponses enregistrées).
- [x] Aucun appel ne combine schéma et outils (test dédié sur les corps de requête).
- [ ] Suites d'évaluation de l'Explication et de la classification relancées sur le modèle local et résultats publiés : **reporté** (voir Reports).

## Code Map

- `src/usine/adaptateurs/llm/fournisseur.py` -- branche `local` (`openai.AsyncOpenAI`, `OpenAIChatModel`, profil `max_tokens`), `URL_SERVEUR_LOCAL`, `openai.OpenAIError` traduite.
- `src/usine/adaptateurs/llm/registre.py` -- `FOURNISSEUR_LOCAL`, tarif nul de tout modèle `local:*`.
- `src/usine/config/secrets.py` -- `usine_llama_url` (`USINE_LLAMA_URL`).
- `src/usine/composition.py` -- `_cle_et_url` partagé par les deux constructeurs.
- `pyproject.toml`, `uv.lock` -- extra `openai` de `pydantic-ai-slim` ; contrats import-linter : `openai` interdit hors `adaptateurs/llm`.
- `config/llm.yaml`, `evals/explication/README.md` -- documentation du fournisseur `local`.
- Tests : `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/contrat/fournisseur_llm/fabriques.py`, `tests/doublures/transport_llm.py`, `tests/unit/test_composition_llm.py`, `tests/depot/test_import_linter.py`.

## Tasks

- [x] Dépendance `openai` (extra pydantic-ai), contrats import-linter et test de classement.
- [x] Branche `local` de l'adaptateur, registre, secret d'adresse, composition.
- [x] Tests : contrat, schéma/outils séparés, sans clé, URL, coût nul, serveur injoignable, composition.
- [x] Documentation de `config/llm.yaml`.

## Spec Change Log

## Notes de dev

- Réponses `llama-server` au format Chat Completions : les doublures réutilisent le format Mistral.
- Procédure du report (poste avec GPU 8 Go) : `llama-server -m <modèle>.gguf --jinja -ngl 99 --port 8080`, `fournisseur: local` et `modele: <nom>` (classification et explication via `modeles_par_tache` si besoin), puis `uv run python -m evals.explication executer --reel` et `uv run python -m evals.classification executer --reel --donnees <répertoire>`. Le Corpus doit venir d'un autre modèle que celui de la classification (garde-fou AD-19).
- Le modèle quantifié exact (8 Go de VRAM) reste à choisir à la relance ; la qualité de l'appel d'outils dépend du gabarit de chat du GGUF.

## Reports

- Relance réelle des deux suites d'évaluation et publication des résultats : nécessite `llama-server` et un modèle sur le poste, interdits dans ce run. Critère d'acceptation partiellement couvert.

## Résultats des contrôles

Voir le rapport de fin de run (ruff check, ruff format --check, mypy, lint-imports, pytest).

## Revue

Passe unique (2026-10-13), diff `962ff54..e3c6fe0`.

- Medium, corrigé : `USINE_LLAMA_URL` n'était pas validée (schéma `ftp:`, hôte absent, valeur mal formée donnaient une erreur obscure du SDK au premier appel). `_verifier_url_serveur` exige une URL http(s) avec hôte, sans citer la valeur (identifiants possibles) ; test paramétré ajouté.
- Low, rejeté : une URL non locale (poste du réseau interne) reste admise, c'est un usage voulu ; la pseudonymisation s'applique avant tout appel quel que soit le fournisseur.
- Low, rejeté : `gratuit=True` pour `local` est cohérent (coût estimé déjà nul).
- Vérifié sans écart : aucune clé exigée ni lue pour `local` (clé factice `sans-cle`, jamais journalisée), contrats import-linter et test de classement à jour pour `openai`, cas `local` dans la suite de contrat `FournisseurLLM`, `contrats/` et `ports/` intacts, séparation schéma/outils testée.
- Report vérifié : la relance réelle des suites d'évaluation est consignée (Reports, `deferred` du front matter, procédure dans les notes de dev) ; critère d'acceptation laissé ouvert, donc statut `review`.
