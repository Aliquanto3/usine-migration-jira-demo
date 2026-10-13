---
title: "Story 6.12 : [BONUS] Mode LLM local"
type: 'feature'
created: '2026-10-13'
status: 'in-review'
baseline_revision: '962ff5453a900b4a4180082493318d46fde9e167'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
deferred:
  - summary: >-
      Relance des suites d'évaluation de l'Explication et de la classification sur le modèle local, et publication des résultats.
    evidence: |-
      Critère « And » de la Story 6.12. Le run de livraison interdit tout llama-server et tout appel LLM réel, et n'a pas de GPU.
      La procédure est dans docs/mode-llm-local.md (§ 4). Aucun résultat local sous evals/*/resultats/.
      Le contrat local ne passe que sur faux transport : le comportement réel de b11552 (outils avec --jinja, tool_choice) reste à constater au même moment.
    location: >-
      docs/mode-llm-local.md
    severity: medium
  - summary: >-
      LLAMA_API_KEY et USINE_URL_LLM_LOCAL absentes de .env.example et de VARIABLES_SECRETES.
    evidence: |-
      tests/depot/test_environnement.py:38 liste les variables attendues dans .env.example ; les deux nouvelles variables de Secrets n'y figurent pas.
      .env.example est protégé par une règle de refus de lecture dans cette session : la modification est laissée à l'auteur.
    location: >-
      tests/depot/test_environnement.py:38
    severity: low
---

<intent-contract>

## Intent

**Problem:** La couche LLM ne connaît que deux fournisseurs distants (Anthropic, Mistral). Si la banque refuse tout LLM distant, le Palier 2 et l'Agent tombent (FR-37, H-13, risque « LLM refusé par la banque »).

**Approach:** Un troisième fournisseur `local` derrière le même adaptateur `FournisseurPydanticAI` : `llama-server` (llama.cpp tag b11552) expose une API compatible OpenAI Chat Completions, servie par `OpenAIChatModel` de Pydantic AI (extra `openai` de `pydantic-ai-slim`). Choix par `fournisseur: local` dans `config/llm.yaml`, sans modification de code ; l'adaptateur rejoint la suite de contrat `FournisseurLLM` (AD-13, AD-20).

## Boundaries & Constraints

**Always:** même port, mêmes deux méthodes : `generer_structure` en Tool Output sans autre outil, `executer_agent` en `output_type=str` avec les seuls outils reçus, jamais combinés. Aucune clé exigée pour `local` (`LLAMA_API_KEY` facultative, envoyée si présente). URL par défaut `http://127.0.0.1:8080/v1`, remplaçable par la variable `USINE_URL_LLM_LOCAL`. Le modèle local figure au registre (coût nul, `gratuit=True`) : `local:ministral-3-8b` (alias `--alias` de llama-server pour `mistralai/Ministral-3-8B-Instruct-2512-GGUF`, Q4_K_M ≈ 5 Go, Apache 2.0, français). `openai` n'est importable que dans `adaptateurs/llm/` (import-linter). Tests sans réseau : faux transport HTTP.

**Never:** aucun appel LLM réel, aucun `llama-server` lancé, aucune lecture de `.env`. Aucune modification de `src/usine/contrats/` ni `src/usine/ports/` (`ConfigLLM.fournisseur` est déjà une chaîne libre). Ne pas toucher `rendu/`, `sprint-status.yaml`. Pas de second adaptateur parallèle : `local` réutilise `FournisseurPydanticAI` (reprise 429, espacement, températures).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sortie structurée locale | `fournisseur: local`, réponse Chat Completions avec appel de l'outil `reponse` | `ReponseStructuree` valide, `version_modele = "local:ministral-3-8b"`, requête sans autre outil que `reponse` | — |
| Tour d'Agent local | outils reçus, réponse `tool_calls` puis texte | outil exécuté, texte rendu, requête sans outil `reponse` | outil non reçu → `UsineErreur` |
| Sans clé | `LLAMA_API_KEY` absente | adaptateur construit (pas d'erreur « variable absente ») | — |
| URL configurée | `USINE_URL_LLM_LOCAL=http://hote:9000/v1` | requêtes envoyées à `http://hote:9000/v1/chat/completions` | — |
| Serveur injoignable | erreur de connexion du transport | `UsineErreur` qui nomme `local:…` et invite à démarrer `llama-server` à l'URL | pas de trace brute du SDK |
| 429 local | `llama-server` saturé renvoie 429 | même reprise que les autres fournisseurs | `UsineErreur` après `tentatives_max` |

</intent-contract>

## Code Map

- `src/usine/adaptateurs/llm/fournisseur.py` -- `FOURNISSEURS` (l.55), `VARIABLES_CLE` (l.58), `_executer` (l.276, tuple d'exceptions traduites : y ajouter `openai.APIError`, et traduire l'erreur de connexion en message dédié), `construire_fournisseur_llm` (l.367 : contrôle de clé l.383 à rendre facultatif pour `local`, branche de construction l.388). Ajouter `URL_LLM_LOCAL_DEFAUT`. Modèle : `OpenAIChatModel(modele, provider=OpenAIProvider(base_url=..., api_key=..., http_client=client_http))`, reprises SDK coupées si le client est créé ici (`max_retries=0`, comme Anthropic l.389).
- `src/usine/adaptateurs/llm/registre.py` -- `REGISTRE` (l.51) : ajouter `local:ministral-3-8b`, prix nuls, débit élevé (pas d'espacement utile), `gratuit=True`, température acceptée.
- `src/usine/adaptateurs/llm/__init__.py` -- docstring (paquets autorisés) et exports (`URL_LLM_LOCAL_DEFAUT`).
- `src/usine/config/secrets.py` -- `Secrets` : ajouter `llama_api_key: SecretStr | None`, `usine_url_llm_local: str | None`.
- `src/usine/composition.py` -- `construire_fournisseur` (l.~330) et `construire_fournisseurs_par_tache` (l.~370) : dict `cles` (l.365, l.387) à étendre à `local`, passer l'URL au constructeur ; docstrings.
- `config/llm.yaml` -- commentaire de `fournisseur` : ajouter `local` (llama-server, sans clé) ; bloc commenté « mode local » prêt à décommenter (`fournisseur: local`, `modele: ministral-3-8b`, `modeles_par_tache` local).
- `pyproject.toml` -- `pydantic-ai-slim[anthropic,mistral,openai]==2.55.0` (l.19) ; ajouter `openai` aux listes `forbidden_modules` qui citent `mistralai` et au contrat AD-12 (l.259-268 : nom, `forbidden_modules`, `ignore_imports`). `uv lock --offline` puis `uv sync --offline` (openai 3.29.0 est dans le cache uv).
- `tests/depot/test_import_linter.py` -- `NOM_ISOLATION_LLM` (l.19) suit le nouveau nom ; `MODULES_DES_DEPENDANCES["pydantic-ai-slim"]` (l.41) et `AUTORISATIONS["usine.adaptateurs"]` (l.86) gagnent `openai`.
- `tests/unit/generateur/test_corpus.py` -- `SDK_FOURNISSEURS` (l.35) gagne `openai`.
- `tests/doublures/transport_llm.py` -- `MODELES` gagne `local: ministral-3-8b` ; `reponse_outil`/`reponse_texte`/`trop_de_requetes` servent `local` au format OpenAI Chat Completions (même forme que `_mistral`, `id` d'appel libre) ; `fournisseur_scripte` inchangé sinon.
- `tests/contrat/fournisseur_llm/fabriques.py` -- `FABRIQUES` (l.~95) : ajouter `("local", _fabrique_enregistree("local"))`.
- `tests/unit/adaptateurs/llm/test_fournisseur.py` -- tests paramétrés par fournisseur (l.63-261) : étendre à `local` là où le format le permet ; `test_cle_absente_nomme_la_variable` ne concerne que les fournisseurs distants ; `test_registre_quotas_et_prix` (l.221).
- `tests/unit/test_composition*.py` / `tests/unit/config/` -- tests existants de `construire_fournisseur` et `Secrets` à compléter (grep `construire_fournisseur(`).
- `docs/fiche-outillage.md` (l.50) -- remplacer « Aucun mode LLM local » par le mode livré ; `docs/mode-llm-local.md` (nouveau) -- procédure.
- Lecture seule : `evals/explication/__main__.py`, `evals/classification/__main__.py` (option `--reel` lit `config/llm.yaml` de `--racine`) ; `evals/classification/suite.py:168` (`verifier_ad19` : le modèle local diffère de `modele_corpus`).

## Tasks & Acceptance

**Execution:**
- `pyproject.toml`, `uv.lock` -- extra `openai`, interdits import-linter, verrou hors ligne -- dépendance du modèle OpenAI de Pydantic AI, isolée comme les autres SDK (AD-12). Si `uv lock --offline` échoue, HALT de la tâche et le signaler (ne pas toucher au réseau).
- `src/usine/adaptateurs/llm/registre.py` -- entrée `local:ministral-3-8b` -- le registre est exigé par `tarif()` et le coût (NFR-9).
- `src/usine/adaptateurs/llm/fournisseur.py`, `__init__.py` -- fournisseur `local` (clé facultative, `url_base` en paramètre mot-clé de `construire_fournisseur_llm`, défaut `URL_LLM_LOCAL_DEFAUT`), erreurs `openai` traduites, connexion refusée nommée -- FR-37 via le même port.
- `src/usine/config/secrets.py`, `src/usine/composition.py` -- `LLAMA_API_KEY`, `USINE_URL_LLM_LOCAL` transmis -- choix par configuration seule (H-23, AD-19).
- `config/llm.yaml` -- documenter `local` et le bloc commenté -- le changement de fournisseur se fait ici.
- `tests/doublures/transport_llm.py`, `tests/contrat/fournisseur_llm/fabriques.py` -- `local` dans la suite de contrat -- AD-20.
- `tests/unit/adaptateurs/llm/test_fournisseur.py`, tests de composition et de `Secrets`, `tests/depot/test_import_linter.py`, `tests/unit/generateur/test_corpus.py` -- couvrir la matrice I/O (URL, sans clé, injoignable, 429, structure sans outil, agent sans outil `reponse`) -- non-régression.
- `docs/mode-llm-local.md`, `docs/fiche-outillage.md` -- procédure : télécharger le GGUF Q4_K_M, lancer `llama-server` b11552 (`-m … --alias ministral-3-8b --jinja -ngl 99 -c 16384 --port 8080`), basculer `config/llm.yaml`, relancer `uv run python -m evals.explication executer --reel` et `uv run python -m evals.classification executer --reel`, publier les résultats sous `evals/*/resultats/` ; état : relance non faite dans ce run (aucun llama-server autorisé).

**Acceptance Criteria:**
- Given `config/llm.yaml` avec `fournisseur: local` et `modele: ministral-3-8b`, when `construire_fournisseur(racine)` est appelé sans aucune clé, then il rend un `FournisseurLLM` de `version_modele` `local:ministral-3-8b` sans appel réseau.
- Given la suite `tests/contrat/fournisseur_llm/`, when elle s'exécute, then les cas `factice`, `anthropic`, `mistral` et `local` passent tous, et aucune requête locale ne déclare à la fois l'outil de sortie `reponse` et un outil d'Agent.
- Given le code produit, when `uv run lint-imports` s'exécute, then `openai` n'est importé qu'en `usine.adaptateurs.llm`.
- Given `docs/mode-llm-local.md`, when un lecteur suit la procédure, then il dispose des commandes exactes de lancement du serveur, de bascule et de relance des deux suites d'évaluation.

## Spec Change Log

## Review Triage Log

### 2026-10-13 — Review pass
- verdicts: 27 findings — high 0, medium 7, low 15, false 5, maybe-false 0
- findings:
  - `[medium]` `[defer]` (blind) Critère « suites d'évaluation relancées et publiées » non rempli — exclu par les contraintes du run (aucun llama-server, aucun appel réel) ; reporté dans `deferred` avec la procédure.
  - `[low]` `[defer]` (blind) `.env.example` et `VARIABLES_SECRETES` sans `LLAMA_API_KEY` ni `USINE_URL_LLM_LOCAL` — réel ; `.env.example` est sous règle de refus dans cette session, reporté dans `deferred`.
  - `[false]` `[reject]` (blind) Le « mode local » accepte une URL distante et y envoie la clé — l'URL est choisie par l'opérateur (serveur sur le réseau local légitime) ; le défaut est la boucle locale, rien ne part ailleurs sans configuration explicite.
  - `[medium]` `[patch]` (blind) Un délai dépassé est annoncé « serveur injoignable » — `openai.APITimeoutError` hérite d'`APIConnectionError` ; `_injoignable` exclut désormais les délais, test ajouté.
  - `[low]` `[patch]` (blind) 503 « Loading model » et 401 `--api-key` non guidés — documentés dans `docs/mode-llm-local.md` (attendre `/health`, `LLAMA_API_KEY`).
  - `[low]` `[patch]` (blind) Suite de contrat locale sur réponses au format Mistral, docstrings du faux transport périmées — le format Chat Completions est le même ; docstrings corrigées.
  - `[low]` `[patch]` (blind) Alias imposé par le registre, changement de GGUF invisible de `version_modele` — même règle que les autres fournisseurs (registre exigé) ; contrainte documentée (alias et entrée de registre par modèle ou quantification).
  - `[low]` `[reject]` (blind) Tests manquants ou fragiles (par tâche en local, 500 local, attribut privé `_url_base`) — le chemin par tâche local est inatteignable avec un seul modèle local ; le 500 local est couvert par `test_autre_erreur_http_sans_reprise_ni_cle[local]` ; le routage d'URL est vérifié par `test_local_url_par_defaut_et_url_configuree`.
  - `[medium]` `[patch]` (blind) Assertion `max_tokens` affaiblie pour tous les fournisseurs — même cause que la ligne `max_completion_tokens` ci-dessous ; assertion stricte rétablie.
  - `[low]` `[patch]` (blind) `outils/generer_corpus.py`, `evals/explication/README.md`, docstring `TarifModele.gratuit` ne citent que deux fournisseurs — mention de `local` ajoutée.
  - `[low]` `[patch]` (blind) `docs/mode-llm-local.md` incomplet (installation b11552, `hf download`, tenue en VRAM non mesurée) — complété.
  - `[false]` `[reject]` (blind) `tiktoken` ferait un appel réseau — le source de `pydantic_ai.models.openai` ne référence pas `tiktoken` ; aucun comptage de jetons local dans le chemin d'appel.
  - `[low]` `[reject]` (blind) Repli `self._url_base or URL_LLM_LOCAL_DEFAUT` redondant, `url_base` ignoré pour les distants — sans effet observable.
  - `[medium]` `[patch]` (edge) Délai dépassé classé injoignable — groupé avec la ligne correspondante ; corrigé.
  - `[low]` `[reject]` (edge) URL malformée (`http://[::1`) : `InvalidURL` brute à la construction — variable saisie à la main, rare ; la correction ajoute une garde.
  - `[low]` `[reject]` (edge) URL sans schéma annoncée « injoignable » — le message cite l'URL fautive, l'opérateur la voit.
  - `[low]` `[patch]` (edge) 503 pendant le chargement du modèle — groupé avec la ligne 503/401 ; documenté.
  - `[medium]` `[patch]` (edge) `max_completion_tokens` envoyé au lieu de `max_tokens` — vérifié dans le profil Pydantic AI (`openai_chat_supports_max_completion_tokens`, défaut vrai) ; profil local à `False`, assertion stricte.
  - `[low]` `[patch]` (edge) Autre GGUF refusé hors registre — groupé avec la ligne alias/registre ; documenté.
  - `[medium]` `[patch]` (verification-gap, autre) Délai dépassé classé injoignable — groupé ; corrigé.
  - `[medium]` `[defer]` (intent) Clause d'évaluation non livrée — groupée avec la première ligne.
  - `[low]` `[defer]` (intent) Contrat local éprouvé sur faux transport, pas sur un llama-server réel — exclu par les contraintes du run ; groupé avec la relance des évaluations.
  - `[low]` `[patch]` (intent) Réponses locales au format Mistral — groupé avec la ligne du faux transport.
  - `[false]` `[reject]` (intent) `config/llm.yaml` ne désigne pas `local` — le critère est conditionnel (« When … désigne ») ; Anthropic reste le défaut (H-23) et le bloc local est prêt.
  - `[false]` `[reject]` (intent) `SDK_FOURNISSEURS` sans `openai` — `tests/unit/generateur/test_corpus.py:39` contient déjà `"openai"`.
  - `[low]` `[reject]` (intent) Test d'URL sur attribut privé — groupé avec la ligne des tests fragiles ; le routage réel est couvert ailleurs.
  - `[false]` `[reject]` (intent) Aucune revue dans le diff — la revue est cette passe.

## Design Notes

llama-server parle OpenAI (`/v1/chat/completions`, outils avec `--jinja`) : un modèle Pydantic AI standard suffit, d'où le choix de l'extra `openai` plutôt qu'un adaptateur HTTP maison. Ministral 3 8B : éditeur français (cohérent avec H-23), appel d'outils natif, GGUF officiel, Q4_K_M dans 8 Go de VRAM avec un contexte de 16 k.

Critère « suites d'évaluation relancées et résultats publiés » : non réalisable sans GPU ni llama-server dans ce run ; la procédure est livrée et le constat est reporté dans `deferred` à la clôture.

## Verification

**Commands:**
- `uv run --no-sync python outils/controle_rapide.py` -- expected: vert pendant le développement.
- `uv run pytest -q tests/contrat/fournisseur_llm tests/unit/adaptateurs/llm tests/depot/test_import_linter.py` -- expected: tout passe.
- Suite complète une fois à la fin : `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest -q` -- expected: tout vert.
