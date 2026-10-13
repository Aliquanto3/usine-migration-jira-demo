---
title: 'Story 6.12 : [BONUS] Mode LLM local'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_revision: '962ff5453a900b4a4180082493318d46fde9e167'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      AC 2 : relance réelle des deux suites avec llama-server et GPU 8 Go, et commit des résultats, à faire par un humain (procédure dans docs/mode-llm-local.md)
    evidence: |-
      Le run interdisait tout appel LLM réel et tout llama-server réel ; la procédure est livrée, l'exécution non.
    location: >-
      docs/mode-llm-local.md
    severity: medium
  - summary: >-
      Les réponses « local » rejouées sont construites au format Chat Completions, pas capturées sur un vrai llama-server b11552.
    evidence: |-
      Non vérifié : tool_choice en mode Tool Output, max_completion_tokens et format des arguments d'outil côté llama-server. À trancher en capturant une réponse réelle lors de la relance de l'AC 2 et en la versionnant comme fixture.
    location: >-
      tests/doublures/transport_llm.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** La couche LLM ne connaît que des fournisseurs distants (Anthropic, Mistral) ; si la banque refuse tout LLM distant, le Palier 2 et la démo tombent (FR-37, AD-13).

**Approach:** Un troisième fournisseur `local` dans `config/llm.yaml`, servi par `llama-server` (llama.cpp, tag b11552) via son API compatible OpenAI (`/v1/chat/completions`), branché dans le même `FournisseurPydanticAI` avec le modèle OpenAI de Pydantic AI. Il passe la suite de contrat `FournisseurLLM` sur réponses enregistrées, et une procédure documentée relance et publie les deux suites d'évaluation avec ce fournisseur.

## Boundaries & Constraints

**Always:** `generer_structure` en mode Tool Output sans autre outil, `executer_agent` en `output_type=str` avec les seuls outils reçus (jamais combinés). Aucune clé exigée pour `local` ; URL de base lue dans `USINE_LLM_LOCAL_URL` (défaut `http://127.0.0.1:8080/v1`). Modèle `local:<alias>` au registre, prix nul, `gratuit=True`, température acceptée. Erreurs du serveur (injoignable, HTTP 5xx, réponse hors schéma) → `UsineErreur` nommant `local:<modele>`, reprise sur 429 inchangée. `openai` n'est importé que dans `adaptateurs/llm/` (import-linter). Tests sans réseau.

**Never:** aucun appel LLM réel ni `llama-server` réel ; pas de modification de `src/usine/contrats/` ni `src/usine/ports/` (la config de l'URL passe par `Secrets`, hors contrats) ; ne pas toucher `rendu/`, `ia/agent`, `sprint-status.yaml` ; pas de clé d'API pour `llama-server` (`--api-key`) ; pas de téléchargement de modèle ni de binaire dans le dépôt.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sortie structurée | `fournisseur: local`, réponse Chat Completions avec appel de l'outil `reponse` | `ReponseStructuree` validée, `version_modele` `local:qwen3-8b`, coût estimé 0 | — |
| Tour d'Agent | réponse demandant un outil reçu puis texte | outil exécuté, conversation rendue | outil non reçu : `UsineErreur` |
| Sans clé | aucune variable de clé | adaptateur construit | — |
| URL | `USINE_LLM_LOCAL_URL=http://h:9000/v1` | requêtes vers `http://h:9000/v1/chat/completions` | absente : défaut `127.0.0.1:8080/v1` |
| Serveur injoignable | erreur de connexion du transport | `UsineErreur` « local:… : appel au fournisseur LLM en échec » | Passage échoue en nommant l'étape (comportement existant) |
| Modèle hors registre | `modele: autre` | `UsineErreur` du registre listant les modèles connus | — |

</intent-contract>

## Code Map

- `pyproject.toml` -- dépendance `pydantic-ai-slim[anthropic,mistral]==2.55.0` : ajouter l'extra `openai` (`uv add`, met à jour `uv.lock` ; `openai` 3.29.0 se résout) ; import-linter : ajouter `openai` partout où figure `mistralai` (listes `forbidden_modules` des couches, contrat « pydantic_ai, anthropic, mistralai : adaptateurs/llm seulement » l. 258-268 avec ses `ignore_imports`).
- `tests/depot/test_import_linter.py` -- vérifie que chaque dépendance directe est classée ; à faire passer.
- `tests/unit/generateur/test_corpus.py:35` -- `SDK_FOURNISSEURS` : ajouter `openai`.
- `src/usine/adaptateurs/llm/fournisseur.py` -- `FOURNISSEURS` (l. 55), `VARIABLES_CLE` (l. 58, `local` sans clé), `_executer` (l. 268 : attraper aussi `openai.APIError`), `construire_fournisseur_llm` (l. 369 : branche `local` avec `OpenAIChatModel` + `OpenAIProvider(openai_client=AsyncOpenAI(base_url=…, api_key=…, http_client=client_http, max_retries=0))`, nouveau paramètre mot-clé `url_local`).
- `src/usine/adaptateurs/llm/registre.py` -- `REGISTRE` : entrée `local:qwen3-8b` (prix 0, 600 requêtes/min, `gratuit=True`).
- `src/usine/adaptateurs/llm/__init__.py` -- exporter la constante d'URL par défaut si ajoutée.
- `src/usine/config/secrets.py` -- `Secrets.usine_llm_local_url: str | None`.
- `src/usine/composition.py:328-397` -- `construire_fournisseur` et `construire_fournisseurs_par_tache` : passer `url_local` ; `cles` sans entrée `local` (clé vide acceptée).
- `tests/doublures/transport_llm.py` -- `MODELES["local"]`, réponses au format Chat Completions d'OpenAI pour `reponse_outil`/`reponse_texte`/`trop_de_requetes` (le format Mistral en est très proche) ; `fournisseur_scripte` fonctionne pour `local`. Vérifier si le SDK `openai` utilise `httpx` ou `httpx2` et fournir le bon client simulé.
- `tests/contrat/fournisseur_llm/fabriques.py:93` -- ajouter `("local", _fabrique_enregistree("local"))`.
- `tests/unit/adaptateurs/llm/test_fournisseur.py` -- `FOURNISSEURS` (l. 31) étendu à `local` là où c'est pertinent ; tests propres à `local` (sans clé, URL, injoignable).
- `tests/unit/test_composition_llm.py` -- construction via `config/llm.yaml` `fournisseur: local`.
- `config/llm.yaml` -- commentaire : valeur `local` et retrait de `modeles_par_tache` (modèles Anthropic) en mode local.
- `docs/mode-llm-local.md` (nouveau) -- installation `llama-server` b11552, modèle `Qwen3-8B-Q4_K_M.gguf` (≈ 5 Go, tient dans 8 Go de VRAM), lancement, configuration, relance et publication des deux suites.
- `docs/fiche-outillage.md:50` -- « Aucun mode LLM local n'est livré » à mettre à jour.
- `evals/classification/README.md`, `evals/explication/README.md` -- renvoi vers la procédure locale.
- Lecture seule : `src/usine/contrats/config.py:442` (`ConfigLLM`, gelé), `src/usine/contrats/versions.py:51` (`version_modele`), `evals/*/__main__.py` (passent par la composition : rien à changer).

## Tasks & Acceptance

**Execution:**
- `pyproject.toml`, `uv.lock` -- extra `openai`, règles import-linter -- isolation AD-12.
- `src/usine/adaptateurs/llm/registre.py`, `fournisseur.py`, `__init__.py` -- fournisseur `local` -- AD-13.
- `src/usine/config/secrets.py`, `src/usine/composition.py` -- URL et construction sans clé -- choix par configuration.
- `tests/doublures/transport_llm.py`, `tests/contrat/fournisseur_llm/fabriques.py` -- réponses enregistrées OpenAI, suite de contrat -- AC 1.
- `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/unit/test_composition_llm.py`, `tests/unit/generateur/test_corpus.py` -- cas de la matrice.
- `config/llm.yaml`, `docs/mode-llm-local.md`, `docs/fiche-outillage.md`, `evals/*/README.md` -- procédure de relance et de publication -- AC 2.

**Acceptance Criteria:**
- Given `config/llm.yaml` avec `fournisseur: local` et `modele: qwen3-8b`, when la composition construit le fournisseur, then c'est un `FournisseurLLM` de version `local:qwen3-8b`, sans clé, vers `USINE_LLM_LOCAL_URL`.
- Given l'adaptateur local sur réponses enregistrées, when la suite `tests/contrat/fournisseur_llm` s'exécute, then tous ses tests passent pour `local`, et la requête Tool Output ne déclare que l'outil `reponse` et celle de l'Agent que les outils reçus.
- Given la procédure `docs/mode-llm-local.md`, when un humain dispose de `llama-server` et d'un GPU 8 Go, then elle donne les commandes exactes pour relancer `evals.classification` et `evals.explication` en mode réel local et publier leurs résultats (fichiers `resultats/`, historique) par un commit.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass
- verdicts: 25 findings — high 0, medium 6, low 13, false 4, maybe-false 2
- findings:
  - `[medium]` `[patch]` (blind) Mode de réflexion de Qwen3 actif par défaut, qui consomme `max_jetons_sortie` et tronque l'appel d'outil — `--reasoning-budget 0` ajouté au lancement, raison expliquée dans `docs/mode-llm-local.md`.
  - `[low]` `[patch]` (blind) « aucun appel sortant » surestimé si `USINE_LLM_LOCAL_URL` vise un hôte distant — formulation conditionnée à une URL du poste, Pseudonymisation rappelée.
  - `[false]` `[reject]` (blind) Variables de proxy appliquées à l'appel local — l'Edge Case Hunter a vérifié que `HTTP_PROXY`/`HTTPS_PROXY` ne détournent pas `127.0.0.1`.
  - `[low]` `[patch]` (blind) Assertion `max_tokens` relâchée pour tous les fournisseurs — clé exacte par fournisseur rétablie (`max_completion_tokens` pour `local`).
  - `[low]` `[patch]` (blind) Test hors schéma vert même si le transport s'épuise — nombre de requêtes et `UnexpectedModelBehavior` vérifiés, réponses distinctes.
  - `[medium]` `[patch]` (blind) URL non vérifiée à travers la composition — même cause que la constatation vérification ; test `test_url_locale_transmise_aux_adaptateurs`, rouge si l'on retire les deux `url_local=` (mutation rejouée).
  - `[medium]` `[patch]` (blind) `modeles_par_tache` laissé en mode local : erreur sans indice — l'erreur est préfixée `config/llm.yaml, modeles_par_tache.<tache>`, test ajouté.
  - `[low]` `[patch]` (blind) Libellé `local:qwen3-8b` sans lien avec le modèle servi — `--alias qwen3-8b` ajouté ; quantification et tag llama.cpp à citer dans le commit des résultats.
  - `[medium]` `[patch]` (blind) `-c 16384` limite sur 8 Go, et les slots parallèles divisent le contexte — `-c 8192 -np 1`.
  - `[low]` `[patch]` (blind) 503 pendant le chargement — attendre que `GET /health` renvoie 200.
  - `[low]` `[patch]` (blind) Report de l'AC 2 absent du journal des reports — entrée ajoutée à `deferred-work.md`.
  - `[maybe-false]` `[reject]` (blind) Spine d'architecture non mis à jour ; tiktoken pourrait télécharger — tiktoken ne sert qu'au comptage de jetons de Pydantic AI, inutilisé ici ; au pire low ; le spine est un artefact de planification (le modifier invaliderait le contexte d'epic).
  - `[low]` `[patch]` (blind) Référence AD-12 retirée de la docstring — rétablie.
  - `[low]` `[reject]` (blind) Code Map obsolète (`test_corpus.py` contenait déjà `openai`) — la correction modifierait la spec de ce build.
  - `[low]` `[patch]` (blind) La fiche outillage perd l'information sur l'Agent — note courte conservée, dans la limite de mots de la fiche.
  - `[medium]` `[patch]` (edge) URL malformée : `httpx2.InvalidURL` brute à la construction — `UsineErreur` nommant `USINE_LLM_LOCAL_URL`, test ajouté.
  - `[low]` `[patch]` (edge) `modeles_par_tache` distants en mode local — même cause et même correctif que la constatation correspondante du Blind Hunter.
  - `[medium]` `[patch]` (verification-gap) Transmission de `USINE_LLM_LOCAL_URL` par la composition non testée (mutation : 90 tests verts) — test ajouté, la mutation le fait désormais échouer.
  - `[low]` `[defer]` (intent) AC 2 non tenue au sens littéral (aucun résultat publié) — le run exclut tout llama-server réel ; reportée (`deferred`), procédure livrée.
  - `[maybe-false]` `[defer]` (intent) Réponses locales rejouées construites et non capturées sur llama-server — à trancher par une capture réelle ; si avérée, medium ; reportée.
  - `[low]` `[reject]` (intent) Tenue de 8 Go non mesurée — même cause que la constatation sur le contexte : contexte réduit ; la mesure exige un GPU, interdit ici.
  - `[false]` `[reject]` (intent) `config/llm.yaml` livré reste sur `anthropic` — l'AC est conditionnelle (« When `config/llm.yaml` désigne… ») ; la bascule est documentée.
  - `[false]` `[reject]` (intent) La suite de contrat ne vérifie pas la séparation schéma/outils — `test_structure_en_mode_tool_output_sans_autre_outil`, paramétré avec `local`, vérifie que seul l'outil `reponse` est déclaré.
  - `[low]` `[reject]` (intent) Pas de test des suites d'évaluation avec `local` en rejeu — le rejeu utilise `FournisseurEnregistre`, indépendant du fournisseur configuré ; le test n'apporterait rien.
  - `[false]` `[reject]` (intent) Revue absente — la revue est cette passe.

## Auto Run Result

- **Résumé** : fournisseur `local` (llama-server, API Chat Completions d'OpenAI via `OpenAIChatModel` de Pydantic AI) dans le même `FournisseurPydanticAI` ; sans clé, URL `USINE_LLM_LOCAL_URL` (défaut `http://127.0.0.1:8080/v1`), registre `local:qwen3-8b` à coût nul ; suite de contrat `FournisseurLLM` étendue à `local` ; procédure de relance et de publication des suites d'évaluation.
- **Fichiers** : `pyproject.toml`, `uv.lock` (extra `openai`, import-linter) ; `src/usine/adaptateurs/llm/{fournisseur,registre,__init__}.py` (branche `local`, erreurs d'URL) ; `src/usine/config/secrets.py` (`usine_llm_local_url`) ; `src/usine/composition.py` (URL transmise, erreur de `modeles_par_tache` située) ; `tests/doublures/transport_llm.py`, `tests/contrat/fournisseur_llm/fabriques.py`, `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/unit/test_composition_llm.py`, `tests/depot/test_import_linter.py` ; `config/llm.yaml`, `docs/mode-llm-local.md` (nouveau), `docs/fiche-outillage.md`, `evals/*/README.md`, `deferred-work.md`.
- **Revue** : 15 constatations corrigées (6 medium, 9 low ; 13 entrées après regroupement par cause, dont 5 medium) ; 2 reportées (AC 2, réponses capturées) ; 8 rejetées (raisons au journal ci-dessus). `contrats/` et `ports/` intacts.
- **Revue de suivi recommandée** : oui (5 entrées medium corrigées, 0 high). Risque non vérifié : les correctifs de revue eux-mêmes n’ont pas été relus, en particulier le `except Exception` large autour de `AsyncOpenAI` et le préfixe ajouté aux erreurs de `construire_fournisseurs_par_tache`, qui s’applique aussi aux fournisseurs distants. Correctifs par verdict d’entrée : medium 5, low 8.
- **Vérification** : `ruff check`, `ruff format --check`, `mypy` (349 fichiers), `lint-imports` (15 contrats tenus), `pytest -q` (2842 réussis, 1 échec `test_fiche_outillage::test_tient_en_une_page`, limite de mots, corrigé puis `tests/unit/docs` vert) ; contrôle rapide OK ; mutation sur la transmission de l'URL : rouge.
- **Risques résiduels** : comportement réel de llama-server b11552 (tool calling, `max_completion_tokens`, qualité d'un 8B) non éprouvé ; cibles SM-3 et SM-9 probablement hors d'atteinte en local.

## Design Notes

- **Pourquoi l'API OpenAI de `llama-server`** : c'est son interface native de tool calling (avec `--jinja`) ; le client Mistral enverrait `tool_choice: "any"`, que llama.cpp ne reconnaît pas.
- **URL en variable d'environnement** : `ConfigLLM` est un contrat gelé (`extra` interdit) ; une variable de `Secrets`, comme `USINE_MODE_REPLI`, évite une évolution de contrat pour une adresse propre au poste.
- **AC 2 reportée en partie** : la relance réelle des suites exige `llama-server` et un GPU, interdits dans ce run. Livré : procédure exacte et adaptateur éprouvé ; à faire par un humain : exécuter et commiter les résultats. Consigné au journal des reports.

## Verification

**Commands:**
- `uv run pytest -q tests/contrat/fournisseur_llm tests/unit/adaptateurs/llm tests/unit/test_composition_llm.py tests/depot/test_import_linter.py tests/unit/generateur/test_corpus.py` -- expected: vert.
- `uv run --no-sync python outils/controle_rapide.py` -- expected: vert.
- Fin : `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` -- expected: vert.
