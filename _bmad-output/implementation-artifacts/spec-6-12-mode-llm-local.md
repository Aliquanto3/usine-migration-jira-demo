---
title: 'Story 6.12 : [BONUS] Mode LLM local'
type: 'feature'
created: '2026-10-13'
status: 'review'
baseline_revision: '962ff5453a900b4a4180082493318d46fde9e167'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: "Relance réelle des suites d'évaluation Explication et classification sur llama-server, et publication des résultats"
    evidence: "La consigne du run interdit tout llama-server réel et tout appel LLM ; l'outillage est prêt (fournisseur `llama` dans config/llm.yaml), la procédure est décrite dans docs/fiche-outillage.md et les README des suites."
    severity: medium
---

<intent-contract>

## Intent

**Problem:** La couche LLM ne connaît que des fournisseurs distants (Anthropic, Mistral) ; si la banque refuse tout LLM distant, la démo du Palier 2 est impossible (FR-37).

**Approach:** Un troisième fournisseur `llama` (llama.cpp `llama-server`, tag b11552, API compatible OpenAI) servi par le même `FournisseurPydanticAI` via le modèle OpenAI Chat de Pydantic AI (extra `openai` de `pydantic-ai-slim`), choisi par `config/llm.yaml` sans modification de code ; adresse du serveur par `USINE_LLAMA_URL` (défaut `http://127.0.0.1:8080/v1`), sans clé d'API.

## Boundaries & Constraints

**Always:** l'adaptateur `llama` passe la suite de contrat `FournisseurLLM` (fabrique enregistrée, faux transport, aucun réseau) ; `generer_structure` en Tool Output sans autre outil, `executer_agent` avec les seuls outils reçus, jamais les deux dans une requête ; reprise sur 429 et espacement identiques aux autres fournisseurs, reprises internes du SDK `openai` coupées (`max_retries=0`) ; `openai` importable seulement dans `adaptateurs/llm/` (import-linter) ; le modèle local figure au registre avec un coût nul (`gratuit=True`), donc `cout_llm_eur` nul ; aucune clé exigée pour `llama` (une clé vide n'est pas une erreur).

**Never:** toucher `src/usine/contrats/` ou `src/usine/ports/` (aucun ajout nécessaire) ; changer le fournisseur par défaut de `config/llm.yaml` (Anthropic reste actif) ; lancer un llama-server réel ou un appel LLM réel ; toucher `rendu/`, `ia/agent`, `sprint-status.yaml`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fournisseur local | `fournisseur: llama`, `modele: qwen3-8b-q4_k_m` | adaptateur `llama:qwen3-8b-q4_k_m`, requêtes `POST {USINE_LLAMA_URL}/chat/completions` | — |
| URL absente | `USINE_LLAMA_URL` non défini | défaut `http://127.0.0.1:8080/v1` | — |
| Clé absente | aucune clé, `fournisseur: llama` | construction réussie | — |
| Débit | réponse 429 du serveur | reprise identique à Anthropic/Mistral | au-delà de `tentatives_max` : `UsineErreur` |
| Serveur injoignable | connexion refusée | `UsineErreur` nommant `llama:<modele>` | pas de reprise |
| Modèle hors registre | `fournisseur: llama`, `modele: inconnu` | `UsineErreur` du registre | — |

</intent-contract>

## Code Map

- `pyproject.toml` -- `pydantic-ai-slim[anthropic,mistral]==2.55.0` (l. 19) : ajouter l'extra `openai` ; contrats import-linter « forbidden » de chaque couche (liste blanche, l. ~108 et suivantes) et contrat transverse `pydantic_ai, anthropic, mistralai : adaptateurs/llm seulement` : ajouter `openai` (renommer le contrat transverse en conséquence). Puis `uv lock` et `uv sync` (openai 3.29.0 résolu localement).
- `tests/depot/test_import_linter.py` -- `NOM_ISOLATION_LLM` (l. 19, à aligner sur le nouveau nom) ; `MODULES_DES_DEPENDANCES["pydantic-ai-slim"]` (l. 39) : ajouter `"openai"`.
- `src/usine/adaptateurs/llm/fournisseur.py` -- `FOURNISSEURS`, `VARIABLES_CLE` (l. 55-59), `construire_fournisseur_llm` (l. ~370) : branche `llama` avec `OpenAIChatModel` + `OpenAIProvider(openai_client=AsyncOpenAI(base_url=url, api_key=cle or "sans-cle", http_client=client_http, max_retries=0))` (vérifier les noms exacts dans `pydantic_ai.models.openai` 2.55.0) ; contrôle de clé seulement pour les fournisseurs de `VARIABLES_CLE` ; `_executer` (l. ~260) : traduire aussi `openai.APIError` en `UsineErreur` ; `ModelHTTPError` 429 déjà géré dans `_requete`.
- `src/usine/adaptateurs/llm/registre.py` -- `REGISTRE` : entrée `llama:qwen3-8b-q4_k_m` (prix 0, `gratuit=True`, débit élevé, température acceptée).
- `src/usine/adaptateurs/llm/__init__.py` -- docstring (paquets autorisés) et exports si une constante d'URL par défaut est ajoutée.
- `src/usine/config/secrets.py` -- `Secrets` : `usine_llama_url: str | None = None` (non secret, comme `usine_racine`).
- `src/usine/composition.py` -- `construire_fournisseur` (l. 328) et `construire_fournisseurs_par_tache` (l. 370) : dictionnaire `cles` sans entrée `llama`, transmettre `secrets_usine.usine_llama_url` à `construire_fournisseur_llm` ; docstrings.
- `config/llm.yaml` -- commentaires : fournisseur `llama`, modèle, `USINE_LLAMA_URL` ; valeurs actives inchangées.
- `tests/doublures/transport_llm.py` -- `MODELES`, `_noms_outils` (format OpenAI = format Mistral `function.name`), réponses Chat Completions OpenAI (`llama_outil`, `llama_texte`, `trop_de_requetes`), dispatch `reponse_outil`/`reponse_texte`, `fournisseur_scripte`.
- `tests/contrat/fournisseur_llm/fabriques.py` -- `FABRIQUES` : ajouter `("llama", _fabrique_enregistree("llama"))`.
- `tests/unit/adaptateurs/llm/test_fournisseur.py` -- `FOURNISSEURS` (l. 31) des tests paramétrés : ajouter `llama` ; `test_cle_absente_nomme_la_variable` reste limité aux fournisseurs à clé.
- `tests/unit/generateur/test_corpus.py:35` -- `SDK_FOURNISSEURS` : à vérifier (ajouter `openai` si la liste énumère les SDK interdits au générateur).
- `tests/unit/test_composition_llm.py` -- composition : `fournisseur: llama` sans clé, URL lue dans `USINE_LLAMA_URL`.
- `docs/fiche-outillage.md`, `evals/classification/README.md`, `evals/explication/README.md` -- procédure du mode local et de la relance des suites.

## Tasks & Acceptance

**Execution:**
- `pyproject.toml`, `uv.lock`, `tests/depot/test_import_linter.py` -- extra `openai`, `openai` interdit hors `adaptateurs/llm` dans tous les contrats -- isolation AD-12 conservée.
- `src/usine/adaptateurs/llm/registre.py` -- entrée du modèle local -- coût nul, NFR-9 inchangé.
- `src/usine/adaptateurs/llm/fournisseur.py` (+ `__init__.py`) -- fournisseur `llama` (constante `URL_LLAMA_DEFAUT`), sans clé exigée, paramètre `url_llama: str | None` de `construire_fournisseur_llm` -- FR-37, AD-13.
- `src/usine/config/secrets.py`, `src/usine/composition.py` -- `USINE_LLAMA_URL` transmis aux deux constructions -- choix par configuration seule (H-23).
- `config/llm.yaml` -- documenter la bascule locale -- l'auteur bascule sans lire le code.
- `tests/doublures/transport_llm.py`, `tests/contrat/fournisseur_llm/fabriques.py` -- fabrique enregistrée `llama` -- la suite de contrat couvre l'adaptateur local.
- `tests/unit/adaptateurs/llm/test_fournisseur.py`, `tests/unit/test_composition_llm.py` -- couvrir la matrice I/O (URL par défaut et surchargée vue dans `transport.urls`, sans clé, 429, serveur injoignable via un transport qui lève `httpx2.ConnectError` ou équivalent, modèle hors registre, requête structure sans `tools` autres que `reponse`).
- `docs/fiche-outillage.md`, `evals/classification/README.md`, `evals/explication/README.md` -- installation de llama-server b11552, modèle GGUF Qwen3-8B Q4_K_M (~5 Go, tient dans 8 Go de VRAM), commande `llama-server -m <fichier>.gguf --jinja --alias qwen3-8b-q4_k_m -ngl 99 -c 16384 --port 8080`, bascule `config/llm.yaml`, relance des deux suites (commandes existantes) et publication des résultats (`historique.jsonl`, `resultats/`).

**Acceptance Criteria:**
- Given `config/llm.yaml` avec `fournisseur: llama`, when la composition construit le fournisseur, then elle renvoie un adaptateur `llama:<modele>` sans exiger de clé ni modifier de code.
- Given la suite `tests/contrat/fournisseur_llm`, when elle s'exécute, then les fabriques `factice`, `anthropic`, `mistral` et `llama` passent toutes les mêmes tests.
- Given `lint-imports`, when un module hors `adaptateurs/llm` importe `openai`, then un contrat échoue.
- Given les contrôles complets, when ils s'exécutent, then ruff, format, mypy, lint-imports et pytest sont verts.

## Spec Change Log

- La procédure du mode local est dans `docs/mode-llm-local.md` (la fiche d'outillage est plafonnée à 700 mots par `test_tient_en_une_page`) ; la fiche, les README des suites et `config/llm.yaml` y renvoient.

## Review Triage Log

### 2026-10-13 — Review pass
- verdicts: 28 findings — high 0, medium 8, low 16, false 3, maybe-false 1
- findings:
  - `[low]` `[reject]` (blind) Aucune clé possible pour un llama-server lancé avec `--api-key` — poste local de démo, cas rare ; le correctif ajoute une variable et un câblage (surface nouvelle).
  - `[medium]` `[patch]` (blind) Mode réflexion de Qwen3 actif, budget de sortie de 300 jetons consommé avant l'outil `reponse` — `--reasoning-budget 0` ajouté à la commande documentée.
  - `[low]` `[patch]` (blind) 503 « Loading model » non repris, message peu explicite, 429 de la doublure au format Mistral — doublure au format d'erreur OpenAI, attente de `/health` documentée ; reprise du 503 non ajoutée (branche de plus pour un cas évité par la procédure).
  - `[low]` `[patch]` (blind) `USINE_LLAMA_URL` absente de `.env.example`, adresse non validée — ligne ajoutée à `.env.example` ; validation rejetée (garde de plus, erreur déjà levée au premier appel).
  - `[low]` `[reject]` (blind) Bascule vers `llama` avec `modeles_par_tache` Anthropic conservé — l'erreur du registre nomme `llama:claude-haiku-5-5` et liste les modèles connus ; `config/llm.yaml` et la doc disent de retirer le bloc ; le correctif ajouterait une branche.
  - `[medium]` `[patch]` (blind) Le test de composition ne prouve pas la transmission de l'URL — test ajouté sur `construire_fournisseur` et `construire_fournisseurs_par_tache` (enregistreur de `url_llama`).
  - `[medium]` `[patch]` (blind) Assertion `max_tokens` assouplie pour tous, `max_completion_tokens` peut-être ignoré par llama-server — profil OpenAI de l'adaptateur `llama` : `max_tokens` envoyé ; assertion stricte rétablie.
  - `[low]` `[patch]` (blind) Coût nul non testé, sémantique de `gratuit` — assertion `cout_estime_eur(...) == 0`, docstring de `gratuit` complétée.
  - `[low]` `[patch]` (blind) Adaptateurs non fermés dans les nouveaux tests — `fermer()` appelé.
  - `[low]` `[patch]` (blind) Documentation incomplète ou contradictoire (README Explication exigeant une clé, source du GGUF, contrôle de disponibilité, `USINE_CLE_PSEUDO`) — README et `docs/mode-llm-local.md` complétés.
  - `[false]` `[reject]` (blind) `tiktoken` téléchargerait ses encodages hors réseau — `pydantic_ai.models.openai` n'importe pas `tiktoken` ; aucun chemin de l'usine ne l'appelle. Fraîcheur d'`openai` 3.29.0 : version verrouillée par `uv.lock`, sans défaut nommé.
  - `[medium]` `[reject]` (blind) Rien ne s'exécute contre un vrai serveur — exclu par l'intent (consigne : aucun llama-server réel, aucun appel LLM) ; déjà consigné dans `deferred`.
  - `[low]` `[patch]` (edge) 503 au chargement — même entrée que la ligne 503 ci-dessus.
  - `[medium]` `[patch]` (edge) Réflexion de Qwen3 — même entrée que la ligne réflexion ci-dessus.
  - `[maybe-false]` `[patch]` (edge) `max_completion_tokens` peut-être ignoré par llama-server b11552 (à vérifier sur la source b11552) — regroupé avec l'entrée `max_tokens` ; `max_tokens`, toujours lu par llama-server, est désormais envoyé.
  - `[low]` `[reject]` (edge) Clé llama-server impossible — même motif que la ligne clé ci-dessus.
  - `[low]` `[reject]` (edge) Adresse sans schéma acceptée — garde supplémentaire ; l'erreur survient au premier appel en nommant `llama:<modele>`.
  - `[low]` `[patch]` (edge) `USINE_LLAMA_URL` absente de `.env.example` — ligne ajoutée.
  - `[low]` `[patch]` (edge) Assertion `max_tokens` assouplie — regroupé avec l'entrée `max_tokens`, égalité stricte rétablie.
  - `[medium]` `[patch]` (verification-gap) URL de l'environnement jamais vérifiée jusqu'à l'adaptateur — même correctif que la ligne composition ci-dessus.
  - `[low]` `[patch]` (verification-gap) Test « coût nul » vérifiant un drapeau non lu — assertion sur `cout_estime_eur`.
  - `[low]` `[reject]` (verification-gap) La spec attribue le coût nul à `gratuit` plutôt qu'aux prix nuls — correctif = modifier la spec.
  - `[medium]` `[reject]` (intent) CA1 exercé sur faux transport, pas sur un llama-server b11552 réel — exclu par l'intent (aucun llama-server réel).
  - `[low]` `[reject]` (intent) `config/llm.yaml` jamais basculé, bloc `modeles_par_tache` à retirer à la main — Anthropic reste actif par choix ; bascule documentée.
  - `[low]` `[reject]` (intent) « Sans combiner schéma et outils » vérifié en unitaire paramétré (`llama` compris) plutôt que dans la suite de contrat — propriété vérifiée sur le même adaptateur ; l'ajouter au contrat demanderait l'introspection des requêtes pour chaque fabrique.
  - `[medium]` `[reject]` (intent) CA2, suites d'évaluation non relancées — exclu par l'intent (aucun appel LLM réel) ; reporté dans `deferred`.
  - `[false]` `[reject]` (intent) Revue absente — la revue est en cours (cette passe).
  - `[false]` `[reject]` (intent) Écriture hors périmètre de l'epic (`pyproject.toml`, `composition.py`, `secrets.py`, `docs/`) — la dépendance se déclare dans `pyproject.toml` et le fournisseur ne se choisit que dans la composition ; aucun préjudice nommé.

## Design Notes

llama-server expose `/v1/chat/completions` au format OpenAI, outils compris avec `--jinja` ; le modèle OpenAI Chat de Pydantic AI y parle sans code spécifique, et `tool_choice` « required » du mode Tool Output est accepté. Le mode Mistral pointé vers llama-server a été écarté (`tool_choice: any` non standard). L'URL passe par l'environnement plutôt que par `config/llm.yaml` : `ConfigLLM` est un contrat gelé et l'URL dépend du poste, comme `USINE_RACINE`. Qwen3-8B Q4_K_M : bon appel d'outils, français correct, ~5 Go de poids plus le contexte dans 8 Go de VRAM ; un autre GGUF se branche par une ligne de registre et `--alias`.

## Verification

**Commands:**
- `uv run --no-sync python outils/controle_rapide.py` -- expected: vert pendant le développement.
- `uv run pytest -q tests/contrat/fournisseur_llm tests/unit/adaptateurs/llm tests/unit/test_composition_llm.py tests/depot/test_import_linter.py` -- expected: vert.
- `uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run lint-imports ; uv run pytest -q` -- expected: tout vert, une fois à la fin.

## Auto Run Result

Status: done

**Résumé.** Troisième fournisseur `llama` (llama.cpp `llama-server`, API compatible OpenAI) servi par `FournisseurPydanticAI` via `OpenAIChatModel` (extra `openai` de `pydantic-ai-slim`), choisi par `fournisseur: llama` dans `config/llm.yaml`, sans clé, adresse par `USINE_LLAMA_URL` (défaut `http://127.0.0.1:8080/v1`), coût nul au registre (`llama:qwen3-8b-q4_k_m`). L'adaptateur passe la suite de contrat `FournisseurLLM` sur faux transport.

**Fichiers.**
- `pyproject.toml`, `uv.lock` : extra `openai` ; `openai` interdit hors `adaptateurs/llm` dans tous les contrats import-linter.
- `src/usine/adaptateurs/llm/fournisseur.py` : branche `llama`, `URL_LLAMA_DEFAUT`, clé non exigée, profil OpenAI qui envoie `max_tokens`, `openai.APIError` traduite.
- `src/usine/adaptateurs/llm/registre.py`, `__init__.py` : modèle local à coût nul, export.
- `src/usine/config/secrets.py`, `src/usine/composition.py` : `USINE_LLAMA_URL` transmis aux deux constructions.
- `config/llm.yaml`, `.env.example` : bascule documentée (valeurs actives inchangées).
- `docs/mode-llm-local.md` (nouveau), `docs/fiche-outillage.md`, `evals/*/README.md` : procédure (llama-server b11552, Qwen3-8B Q4_K_M, `--reasoning-budget 0`, `/health`), relance des suites.
- Tests : fabrique `llama` de la suite de contrat, unitaires paramétrés et propres à llama, composition (URL transmise), import-linter.

**Revue.** 28 constats : 8 correctifs appliqués (3 medium, 5 low ; commit `Fix: Story 6.12, correctifs de revue`), 0 nouveau report, rejets motivés dans le journal de triage (clé llama-server, reprise du 503, validation d'URL, bascule de `modeles_par_tache` : low à surcoût de complexité ; exécution réelle : exclue par la consigne ; 3 faux).

**Revue de suivi recommandée : oui** (3 entrées medium corrigées). Risque nommé : le profil OpenAI fusionné (`merge_profile`) et la commande llama-server documentée n'ont été relus par aucune passe ; leur comportement contre llama-server b11552 n'est pas observé.

**Vérification.** `ruff check`, `ruff format --check`, `mypy`, `lint-imports` (15 contrats tenus), `pytest -q` (2838 réussis, 1 sauté) : tout vert, une fois à la fin ; tests ciblés et contrôle rapide verts pendant le développement.

**Risques résiduels.** Aucun essai contre un vrai llama-server (interdit par la consigne) : `tool_choice: required`, `max_tokens`, `--reasoning-budget 0` et l'empreinte VRAM restent à confirmer ; relance des suites d'évaluation et publication des résultats reportées (`deferred`).
