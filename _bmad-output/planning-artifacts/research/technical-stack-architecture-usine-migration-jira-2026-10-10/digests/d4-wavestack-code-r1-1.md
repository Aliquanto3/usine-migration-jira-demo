# D4 - Digest du code wavestack (couche modeles / cloud)

Source : `agentic-harness-training-demo/src/wavestack/` (chemins relatifs a ce dossier ; `models/X:N` = `src/wavestack/models/X:N`). Lecture locale, faits uniquement. Les numeros de ligne prefixes `~` sont approximatifs.
Contexte : demo pedagogique "harnais agentique" local CPU, Python 3.13 strict (`pyproject.toml:7`, `requires-python = "==3.13.*"`), pas 3.12.

## 1. Carte des modules (`models/`, ~6 950 LOC)

| Fichier | LOC | Responsabilite / elements cles |
|---|---|---|
| `__init__.py` | 1 | docstring seule |
| `cloud_base.py` | 1019 | Base commune des adaptateurs cloud : `CloudEngine` (l.440), `ChatBody`/`ChatEnd` (59/66), `ProviderError` (95), `pace()` (242), `mask_key` (144), FinOps (`call_cost` 283, `record_spend` 372, `session_cap_error` 408), `_refused()` (~578, mapping HTTP -> erreurs), `_check_calls` (804), `run_call()` (840, emet les evenements `model_*`) |
| `openai_chat.py` | 235 | `OpenAIChatEngine` (l.82) : lecture SSE, `tool_calls` fragmentes, raisonnement sous 3 formes (Groq/Mistral/Gemini) |
| `anthropic_messages.py` | 241 | `AnthropicMessagesEngine` (l.63) : SSE `content_block_*`, `tool_use`, blocs `thinking` signes, `pivot_usage` (45) |
| `openai_responses.py` | 284 | Adaptateur Responses API OpenAI (stateless, `store:false`), items `reasoning` chiffres |
| `cloud_api.py` | 42 | Registre `api -> classe` (`ENGINES` l.20) + `create_cloud_engine` (27) |
| `catalog.py` | 1114 | Tableau des modeles locaux + cloud : `ModelEntry` (498), `local_entries` (788), `cloud_entries` (811), editeurs, groupement en cartes. Pure presentation UI |
| `capabilities.py` | 285 | `Capabilities` (32), `capabilities_for` (47, local via GGUF), `cloud_capabilities` (106), `ChannelSplitter` (205, balises `<think>`) |
| `engine.py` | 489 | Port `Engine` (Protocol l.109) + `LlamaCppEngine` (311, llama-cpp-python en process), `CancelToken` (49), `Sampling` (24) |
| `servers.py` | 1077 | Serveurs locaux deja lances : `LlamaServerEngine` (348, `/completion`), `OllamaRawEngine` (534, `/api/generate` raw), `list_served` (920), `open_engine` (1056) |
| `discovery.py` | 320 | Decouverte de GGUF locaux (Ollama, LM Studio, cache HF) : `discover` (244) |
| `load_registry.py` | 316 | Budget memoire, un slot generatif (`LoadRegistry` l.142) ; slot `COMPRESSOR` (l.32) pour Headroom |
| `probe.py` | 431 | Sonde GGUF en process enfant avant premier usage (`probe_file` 179) |
| `gguf_meta.py` | 172 | Lecteur d'en-tete GGUF en Python pur (`read_metadata` 108) |
| `download.py` | 214 | Telechargement de fichiers modele (httpx, `.part`, sha256) |
| `embedding.py` | 149 | Port `Embedder` + llama.cpp / fastembed (RAG) |
| `reranker.py` | 359 | Port `Reranker` + cross-encoder llama.cpp |
| `candidates.py` | 205 | Candidats de token depuis les logits (ecran pedagogique "LLM nu") |

Hors `models/` mais pertinent : `config.py` (`CloudModel` ~l.210, `CloudPricing` 161, `CloudReasoning` 141, `cloud_window` 1169), `net/factory.py` (`create_client` 214), `context/render.py` (traducteurs de corps par `api`), `compression/` (276 LOC), `wavestack.toml` (declarations de modeles).

## 2. Structure du catalogue

Il n'y a pas de fichier de donnees de catalogue. Les modeles cloud sont declares dans `wavestack.toml` (`[[cloud.models]]`, l.~349-720) et valides par le modele Pydantic `CloudModel` (`config.py:~210-290`, classe `_Strict`). Champs :
- Identite : `id` (`^[a-z0-9_]+$`), `provider`, `base_url` (https obligatoire, http seulement loopback), `model`, `api` in {`openai_chat` (defaut), `anthropic_messages`, `openai_responses`} (config.py:~232).
- Auth : `auth_header {name, scheme}` (config.py:125), `extra_headers` (ex. `anthropic-version`), `key_env` (nom de variable d'env, jamais la cle).
- Capacites declarees a la main : `tools: bool`, `reasoning: CloudReasoning` (format field / content_blocks / think_tags / thinking_blocks / reasoning_items, `on`/`off`/`always`/`resend` ; config.py:141-158), `stream_usage`, `max_tokens_field`, `sampling`, `tool_call_extra` (signature de pensee Gemini).
- Taille et quotas : `context` (fenetre native), `window` (override), `tpm` (quota tokens/minute, declaratif), `min_interval_s` (espacement, 0 < x <= 60 ; config.py:252).
- Prix : `pricing {input_usd_per_mtok, output_usd_per_mtok, cache_read_usd_per_mtok?, cache_write_usd_per_mtok?, checked(date)}` (config.py:161-172), saisis a la main avec date de releve (ex. Groq 0.15/0.60, checked 2026-09-29, wavestack.toml:367).
- Autres : `hosting_text`, `training` (yes/no/opt_out), `trial`, `notes_text`, `enabled`, `impacts` (EcoLogits).
- Fenetre effective = `min(window ou configuree, context, tpm//2)` (`config.cloud_window`, config.py:1169-1177) ; entree inutilisable si `tpm//2 <= 1536` (config.py:1180-1184).
- Presets dans `wavestack.toml` : groq (`openai/gpt-oss-120b`, tpm=8000, l.349-370), mistral (`mistral-small-latest`, `min_interval_s=1`, l.376-398), gemini (`gemini-3.5-flash-lite`, l.443), gemma (Google AI Studio, l.488), claude_haiku / claude_sonnet (`anthropic_messages`, l.540 / 570), openai_luna (`openai_responses`, l.637) ; nvidia / openrouter commentes (l.701-716). Pas de preset Azure OpenAI.
- `catalog.py` ne fait que presenter : `ModelEntry` (l.498-547) ajoute editeur (`content/models/publishers.yaml`, regex sur les noms), params, fenetre, capacites, `price_text`. `cloud_entries` (811-869) lit `cfg.cloud_models` et appelle `cloud_capabilities` (capabilities.py:106-121 : `tool_call_parser="openai_chat" if entry.tools`, `reasoning`, `native_context`).
- Aucune capacite "sortie structuree / JSON schema" n'est modelisee.
- Origine des donnees : saisie manuelle de l'operateur (prix, quotas, hebergement) ; pour le local, en-tetes GGUF et Ollama `/api/tags`.

## 3. Espacement des appels / rate limiting

- Algorithme : `pace(entry, cancel)` (cloud_base.py:242-268). Registre global `_last_start: dict[entry.id, monotonic]` + `threading.Lock` (l.239-240). Sous verrou : `start = max(now, previous + interval)` et reservation du creneau ; attente hors verrou via `cancel.wait(delay)` ; si annule, creneau libere ; a l'envoi reel, mise a jour avec l'heure effective. C'est un espacement minimal fixe entre departs, par `entry.id`, thread-safe et annulable. Pas de token bucket, pas de fenetre glissante, pas de comptage de tokens.
- Config : `min_interval_s` par entree (config.py:252). Seul Mistral en a un dans le toml (1 s : "le plan gratuit refuse 429 deux requetes a moins d'une seconde", wavestack.toml:393-395). Groq n'a que `tpm=8000`, utilise uniquement pour dimensionner la fenetre (pas pour freiner).
- Appel : `run_call` (cloud_base.py:861-880) : verif plafond de session -> `pace()` -> reverification ; l'attente n'est pas comptee dans `prompt_ms` / `duration_ms`.
- Jamais lu depuis les en-tetes : docstring l.245-246 ("Never read from x-ratelimit-* headers").
- 429 (`_refused`, cloud_base.py:632-672) : jamais de retry automatique. Lit `Retry-After` (float, l.633-637), classe la portee par regex sur le message (`_quota_scope` l.194-203 : minute / second / day), leve `ProviderError(http_status=429, retry_after_s, quota_scope)` avec des conseils ("attendre N s", "augmenter min_interval_s", "reduire le contexte"). Cas non retentables : quota nul (`x-ratelimit-limit-req-minute: 0`, l.206-210, Mistral sans plan) et credit epuise (`insufficient_quota`, `credit_balance_exhausted`, Anthropic "credit balance is too low" ; l.213-228, 612-630).
- 5xx / `overloaded_error` : erreur "indisponible", jamais retentee (cloud_base.py `status >= 500` apres l.700 ; anthropic_messages.py `_stream_error`). Docstring module cloud_base.py:9 : refus du fournisseur "never retried".
- Seuls retries : boucle d'outils au niveau session (`tools.max_retries=2`, `max_calls=6`, config.py:1039-1044 ; app_session.py:6613+), pour appels d'outils mal formes, pas pour le reseau.
- Plafond de depense de session (`max_session_usd`, defaut 5 $, config.py:~205) : `session_cap_error` (cloud_base.py:408).

## 4. Headroom (adaptateur de compression)

- Quoi : `headroom-ai==0.38.0` (Apache-2.0), extra optionnel `compression` (pyproject.toml:26-28). Adaptateur `compression/headroom_adapter.py` (148 LOC), port `compression/port.py` (`Compressor` Protocol l.22-29, `Compressed`).
- Ce qu'il comprime : resultats d'outils (natifs, reseau, MCP) et extraits RAG d'au moins `[compression] min_chars` (300) dans le contexte principal ; jamais historique, skills, sous-agent (`content/compression.yaml` `limits_text`). Sans ML (`kompress_model="disabled"`) il reduit le texte structure (tableaux JSON, logs) et laisse la prose intacte (headroom_adapter.py:7-10). Ne tient pas compte de la question de l'utilisateur (l.17-18, mesure).
- Branchement : `HeadroomCompressor.compress(text)` emballe le texte en faux message `role:"tool"` dans une conversation de 3 messages, appelle `headroom.compress(messages, model="gpt-4", kompress_model="disabled", protect_recent=0)`, relit le dernier message et ne garde le resultat que si la forme est inchangee (`reply_text`, l.104-113) ; renvoie `Compressed(texte, transforms)`. Charge a la demande dans la session via `LoadRegistry` (slot `COMPRESSOR`), app_session.py:912-918 ; import lourd (litellm, tiktoken) + warm-up.
- Contraintes : mode hors ligne force (`compression/env.py`, `HEADROOM_OFFLINE=1`, `HEADROOM_BEACON=off`, `HEADROOM_UPDATE_CHECK=off`), table tiktoken `cl100k_base` embarquee, pin exact verifie (`missing_fr`, l.50-77).
- Gains mesures notes dans le depot : aucun taux de compression chiffre trouve (docs/guide.md:186-217 ; deferred-work.md). Seuls chiffres : memoire +84 Mo au pic (107 Mo sous Linux), ~40 paquets / 285 Mo sur disque (docs/guide.md:202, 214), latence 2,2 s au pire (premier appel, JSON ~6 600 tokens) puis 0,02 s (`_bmad-output/implementation-artifacts/deferred-work.md:422`). L'UI affiche tokens avant / apres par appel, sans benchmark agrege.

## 5. Adaptateurs OpenAI Chat / Anthropic Messages

Principe commun : le corps JSON est ecrit par `context/render.py` (traducteurs par `api`) ; les adaptateurs l'envoient tel quel en octets (`ChatBody.body`, cloud_base.py:59-63 ; `complete()` ~l.535-560 : `client.stream("POST", base_url+endpoint, content=body.body)`). Ils ne font que lire le flux SSE et le normaliser en `ChatEnd` (cloud_base.py:66-92). Format pivot interne = messages Chat Completions (openai_chat.py:6).

- OpenAI Chat (`openai_chat.py`) :
  - Outils : fragments `delta.tool_calls` accumules par `index` / `id` (l.~200-228), gere appels paralleles, Gemini sans `index`, `extra_content` (thought signature). Les arguments restent des chaines JSON ; `_check_calls` (cloud_base.py:804-817) les `json.loads` et exige un objet, sinon `out.malformed` (boucle de correction cote session).
  - `tool_use_failed` (Groq) en 400 ou dans le flux : fin d'appel avec `provider_error=failed_generation` (cloud_base.py:584-593 ; openai_chat.py:125-136).
  - Sortie structuree : aucune (pas de `response_format` / `json_schema` ; grep negatif dans `src/`). Pas de `tool_choice` non plus. Schemas d'outils passes tels quels (`tools` = liste `{type:function, function:{...}}`, render.py:426).
  - Streaming : SSE obligatoire, `data: [DONE]`, `finish_reason` mappe (`_FINISH` l.72) ; usage via chunk final et `x_groq.usage`. Raisonnement : champs `reasoning` / `reasoning_content`, blocs `thinking` Mistral, balises `<think>`.
  - Erreurs : mapping HTTP 3xx / 400 / 401 / 403 / 404 / 413 / 422 / 429 / 5xx, timeouts, reseau, avec masquage de cle (`mask_key`) ; `ProviderError` a liste fermee, jamais retente.
- Anthropic Messages (`anthropic_messages.py`) :
  - Corps (render.py:~480-528) : `system` joint, resultats d'outils regroupes en blocs `tool_result` dans un message `user`, `tools` avec `input_schema` (renomme depuis `parameters`).
  - Outils : blocs `tool_use`, `input_json_delta` accumules en `partial`, arguments reconstruits en chaine JSON (`{}` si aucun delta) (l.~150-215).
  - Pas de sortie structuree (ni `output_format` ni outil force).
  - Streaming : evenements `message_start` / `content_block_*` / `message_delta` ; `stop_reason` mappe (`_FINISH` l.32) ; `refusal`, `model_context_window_exceeded`, `pause_turn` -> erreur ; flux sans `stop_reason` -> "interrupted". Blocs `thinking` + `signature` et `redacted_thinking` conserves verbatim pour le tour suivant ; `input_transformations` tracees.
  - Usage pivote (`pivot_usage` l.45-60) avec cache lu / ecrit.
- OpenAI Responses (`openai_responses.py`, render.py:~544-600) : `store:false`, `tools` avec `strict:false`, items `reasoning` chiffres renvoyes.

## 6. Dependances

- HTTP : httpx brut (`httpx>=0.28,<0.29`, pyproject.toml:12), client synchrone via `net/factory.create_client` (truststore, proxy du poste, traces, redirections jamais suivies ; factory.py:214-238). Aucun SDK officiel (anthropic, openai, mistralai, google-genai absents des dependances).
- Autres : pydantic 2.13, fastapi / uvicorn, truststore, psutil, llama-cpp-python (inference locale en process), pyyaml, mcp 2.2, anyio, sqlite-vec, ecologits. Extras : `headroom-ai==0.38.0` (litellm et tiktoken en transitif), faiss-cpu, lancedb, codecarbon.
- Textes d'erreur en francais via un systeme `Message` i18n, fortement couple a l'UI et au journal d'evenements.

## 7. Verdict de reutilisation

| Composant | Verdict | Raison |
|---|---|---|
| `pace()` espacement par entree (cloud_base.py:236-268) | Adapter (idee, ~30 LOC) | Simple, thread-safe, annulable ; utile pour Groq free tier. Synchrone + `threading` : a reecrire en asyncio ; seul un intervalle fixe existe, il faut ajouter token bucket RPM/TPM |
| Gestion 429 / `Retry-After` / quota nul / credit epuise (cloud_base.py:194-228, 632-672) | Adapter (classification, pas le code) | Classification utile (minute / jour / credit / quota 0), mais aucun retry automatique : a completer avec backoff (tenacity ou retries du framework). Messages couples a l'UI francaise |
| `CloudModel` / `CloudPricing` declaratifs (config.py:161-290) | Adapter | Bon modele de registre (tpm, min_interval_s, prix dates, capacites) ; prix et quotas maintenus a la main. Aucun framework n'apporte ce registre de quotas |
| `cloud_window` (`tpm//2`, config.py:1169) | Ne pas reutiliser | Specifique au harnais pedagogique a fenetre 4k |
| Adaptateurs `openai_chat` / `anthropic_messages` / `openai_responses` (SSE brut) | Ne pas reutiliser (Pydantic AI / LiteLLM couvrent) | Reimplementation httpx volontaire pour tracer les octets ; pas de sortie structuree ni validation de schema ; providers Groq, Anthropic, OpenAI, Mistral, Google, Ollama deja couverts par les frameworks |
| Parsing des `tool_calls` fragmentes + `_check_calls` | Ne pas reutiliser | Idem ; garder les cas limites comme cas de test (appels paralleles, Gemini sans `index`, `tool_use_failed` Groq, JSON invalide) |
| Sortie structuree Pydantic / agent d'outils | Absent | Rien a reprendre ; Pydantic AI (`output_type`, tools) couvre le besoin |
| `HeadroomCompressor` (compression/headroom_adapter.py) | Adapter ou ignorer | Pertinent seulement pour de gros resultats d'outils JSON / logs (Jira) ; gain non mesure dans le depot ; dependance lourde (285 Mo, litellm, binaires natifs non signes). Pattern "faux message tool" reutilisable ; benchmarker avant adoption |
| `mask_key` et plafond de depense de session | Adapter | Idees simples et utiles ; implementation couplee au journal d'evenements |
| FinOps `call_cost` (cloud_base.py:283-312) | Adapter | Tokens x prix + cache lu / ecrit ; rapide a reprendre |
| `net/factory.create_client` (truststore, proxy) | Adapter si poste verrouille | Utile en contexte entreprise ; Pydantic AI accepte un `http_client` httpx personnalise |
| `llama-cpp-python`, `servers.py` (Ollama raw, llama-server `/completion`) | Ne pas reutiliser | Mode "texte rendu" (le harnais applique le template) ; pour le local, endpoint OpenAI-compatible d'Ollama / llama.cpp via le provider OpenAI du framework |
| `catalog.py`, `discovery.py`, `probe.py`, `gguf_meta.py`, `load_registry.py`, `download.py`, `embedding.py`, `reranker.py`, `candidates.py` | Ne pas reutiliser | Specifiques a l'UI pedagogique et a la gestion memoire de modeles GGUF locaux ; hors perimetre |
