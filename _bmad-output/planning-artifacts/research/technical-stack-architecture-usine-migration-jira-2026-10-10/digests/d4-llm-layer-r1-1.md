# D4 — LLM layer: Pydantic AI vs LangGraph + LiteLLM (round 1, digest 1)

Accessed: 2026-10-10. Budget used: 20 tool calls, 16 distinct sources.
Class legend: P = primary (vendor docs, PyPI, GitHub), S = secondary (press/analysis), A = aggregator/blog (low trust).

## Findings

| # | Claim | Source URL | Publisher | Pub date | Accessed | Confidence | Class |
|---|---|---|---|---|---|---|---|
| F1 | Pydantic AI latest is **2.55.0** (PyPI `info.version`). | https://pypi.org/pypi/pydantic-ai/json | PyPI | 2026-10-09 | 2026-10-10 | High | P |
| F2 | Release cadence is very fast: v2.48.0 (09-22), 2.49 (09-23), 2.50 (09-24), 2.51 (09-25), 2.52 (09-29), 2.53 (10-01), 2.54 (10-02), 2.55 (10-09). The v1 line is still maintained (v1.107.7 on 2026-09-29, "a maintenance release for the v1 line"). Security fixes are backported (2.52.0 / 1.107.7). From 2.55.0, every package requires Python ≥ 3.11. | https://github.com/pydantic/pydantic-ai/releases | GitHub / Pydantic | 2026-09-22 to 10-09 | 2026-10-10 | High | P |
| F3 | Pydantic AI reached V1 in **September 2025** with a promise of no breaking changes until V2. **V2.0.0 stable shipped 2026-06-23**. Its breaking changes are listed in the v2.0.0b1 entry, and the upgrade path goes through v1.107.0. A separate Version Policy page exists but was not read. | https://pydantic.dev/docs/ai/changelog/ (via search snippet) | Pydantic | undated (page) | 2026-10-10 | Medium-high (snippet, not full fetch) | P |
| F4 | Three structured-output modes. **Tool Output** is the default, "supported by virtually all models and has been shown to work very well". **NativeOutput** uses the provider's JSON-schema response format: "not supported by all models, and sometimes comes with restrictions". Gemini 3 can combine native output with function tools, but earlier Gemini models cannot. **PromptedOutput** "is usable with all models, but is often the least reliable approach". | https://pydantic.dev/docs/ai/core-concepts/output/ | Pydantic | undated | 2026-10-10 | High | P |
| F5 | On validation failure the model is asked to retry. The output retry budget defaults to 1 and can be set with `Agent(retries={'output': N})`, per run, or with `ToolOutput(max_retries=N)`. `@agent.output_validator` can raise `ModelRetry`, which suits checks such as "cited ticket IDs exist". | same as F4 | Pydantic | undated | 2026-10-10 | High | P |
| F6 | Native providers include OpenAI, Anthropic, Google (Gemini API), Mistral, Groq, Azure/Foundry, Ollama, vLLM, **LiteLLM**, OpenRouter and others. Other OpenAI-compatible endpoints work through a custom provider. Models are selected with `provider:model` strings. | https://pydantic.dev/docs/ai/models/overview/ | Pydantic | undated | 2026-10-10 | High | P |
| F7 | `FallbackModel` tries models in order on `ModelAPIError` (4xx/5xx, connection errors, timeouts). Validation errors do **not** trigger fallback. Response-based fallback works only without streaming. The docs advise disabling the provider SDK's own retries. `TestModel` and `FunctionModel` are provided for testing. | same as F6 | Pydantic | undated | 2026-10-10 | High | P |
| F8 | LangGraph latest is **1.2.14** (2026-10-06) and requires Python ≥ 3.10. The 1.x line has therefore shipped. The exact 1.0 date was not verified this run. | https://pypi.org/project/langgraph/ | PyPI | 2026-10-06 | 2026-10-10 | High (version) | P |
| F9 | LiteLLM latest stable is **1.104.2** (2026-10-08), with a 1.106.0.dev3 pre-release on 10-09. The release cadence is very high. | https://pypi.org/project/litellm/ | PyPI | 2026-10-08 | 2026-10-10 | High | P |
| F10 | **LiteLLM supply-chain compromise, 2026-03-24.** The malicious PyPI versions 1.82.7 and 1.82.8 were attributed to TeamPCP, which stole the PyPI publishing token. 1.82.8 shipped a `.pth` payload that runs without `import litellm` and harvested SSH keys, cloud credentials and API keys. The versions were live for less than 5 h and transitive dependents were exposed. The claimed root cause (a compromised Trivy scanner in CI) is reported by some outlets only. | https://infoq.com/news/2026/03/litellm-supply-chain-attack/ ; https://www.helpnetsecurity.com/2026/03/25/teampcp-supply-chain-attacks/ | InfoQ; Help Net Security | 2026-03 | 2026-10-10 | High (event); Medium (root cause) | S |
| F11 | LiteLLM structured output: `response_format` accepts a Pydantic model or `json_schema` with `strict`. Listed providers are OpenAI, Azure, Gemini (AI Studio and Vertex), Anthropic, Groq, Ollama, Bedrock, xAI and Databricks. `supports_response_schema()` checks a model, and `litellm.enable_json_schema_validation=True` validates client-side for models without native support. The docs do not say what happens when validation fails, and there is **no built-in re-ask loop**. | https://docs.litellm.ai/docs/completion/json_mode | BerriAI | undated | 2026-10-10 | High | P |
| F12 | Groq's rate-limits page shows "base limits for the **Developer** plan". It sends free-plan users to their console limits page. For openai/gpt-oss-120b, gpt-oss-20b and qwen/qwen3.8-27b it shows **30 RPM / 1K RPD / 8K TPM / 200K TPD**. Llama 3.3 70B and Llama 3.1 8B were not in the table read. | https://console.groq.com/docs/rate-limits | Groq | undated | 2026-10-10 | Medium (the plan label is ambiguous) | P |
| F13 | Groq strict JSON-schema output is available only on gpt-oss-20b, gpt-oss-120b and qwen3.8-27b. `json_object` works on all models. "**Streaming and tool use are not currently supported with Structured Outputs.**" On Groq, the Pydantic AI default ToolOutput mode (F4) is therefore the practical path, rather than NativeOutput. | https://console.groq.com/docs/structured-outputs | Groq | undated | 2026-10-10 | High | P |
| F14 | The official Gemini rate-limits page publishes **no free-tier numbers**. Limits "can be viewed in Google AI Studio" and apply per project. | https://ai.google.dev/gemini-api/docs/rate-limits | Google | undated | 2026-10-10 | High (absence) | P |
| F15 | Secondary reports: on **2025-12-07** Google cut free-tier quotas by 50–92% (2.5 Flash went from about 250 to about 20 RPD) and removed Pro from the free tier. Later 2026 tracker claims (spend caps from 2026-04-01, Flash-only free tier) conflict with each other. | https://agentdeals.dev/gemini-api-pricing-changes ; https://dev.to/anna001/is-free-gemini-25-pro-api-fried-changes-to-the-free-quota-in-2025-200h | agentdeals.dev; DEV | 2026-04-08; 2025 | 2026-10-10 | Low-medium | A |
| F16 | Mistral's free "Experiment" plan is reported as **500K TPM and 1B tokens/month per model**. RPM figures conflict (about 1 RPS vs about 2 RPM). Signup needs phone verification and no card, and data may be used for training (opt-in/out unclear). The official tier page (docs.mistral.ai/deployment/ai-studio/tier) returned **404**. | https://costbench.com/software/llm-api-providers/mistral-ai/free-plan/ (+ aggregators) | costbench / aggregators | 2026 | 2026-10-10 | Low | A |
| F17 | Anthropic structured outputs are **GA**: `output_config.format` with `type: json_schema` and no beta header. The old `output_format` is deprecated and needs the `structured-outputs-2025-11-13` header. Supported on Claude API, Google Cloud and Microsoft Foundry, including Opus 5.5, Sonnet 5.5 and Haiku 5.5. On Amazon Bedrock it is GA only on the legacy integration (Opus 4.6 and older). Strict tool use (`strict: true`) is documented on another page that was not read. | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | Anthropic | undated | 2026-10-10 | High | P |
| F18 | Ollama accepts a JSON schema in `format`, for example `Model.model_json_schema()`. Structured outputs "work through the OpenAI-compatible API via `response_format`", but `json_schema` there is not explicitly confirmed. Ollama Cloud does not support structured outputs. | https://docs.ollama.com/capabilities/structured-outputs | Ollama | undated | 2026-10-10 | High / Medium (OpenAI-compatible detail) | P |
| F19 | llama.cpp `llama-server` converts an OpenAI-style `response_format` json_schema into a grammar. Unsupported keywords are **ignored silently**, so you must validate client-side. A global `--json-schema` flag and a `grammar` field also exist. Older issues (#11847, #11988) report json_schema bugs on /v1/chat/completions. Whether they are fixed was not verified. | https://docs.liquid.ai/deployment/on-device/llama-cpp/structured-output ; https://github.com/ggml-org/llama.cpp/issues/11847 | Liquid AI; GitHub | undated / 2025 | 2026-10-10 | Medium | S/P |

## Criteria table

| Criterion | Pydantic AI | LangGraph + LiteLLM |
|---|---|---|
| Stability / version policy | v1 in Sep 2025, v2 stable on 2026-06-23, v1 line still patched; no-breaking-change promise between majors (F2, F3) | LangGraph 1.2.x (F8); LiteLLM 1.10x with near-daily releases (F9). Pin strictly in both cases. |
| Pydantic-validated structured output | First-class: three modes, Tool Output default works on nearly all models, automatic re-ask on validation failure, `output_validator` + `ModelRetry` (F4, F5) | LiteLLM passes a Pydantic `response_format` through, and client-side validation is optional. The re-ask loop has to be built by hand or with LangChain `with_structured_output` (not verified this run) (F11). |
| Small read-only tool agent (4 tools) | Native agent + tools (F6, F7). Enough for 4 tools without a graph. | LangGraph excels at multi-step stateful graphs, which is overkill for 4 read-only tools. |
| Provider coverage (Groq, Anthropic, OpenAI, Mistral, Gemini, Azure, Ollama/llama.cpp) | All listed natively, plus a custom OpenAI-compatible provider and even LiteLLM as a backend (F6) | LiteLLM covers all of them (F11). This is LiteLLM's core strength. |
| Weak structured-output providers (Groq tools + schema, llama.cpp) | Tool Output default avoids Groq's "no tools with structured outputs" limit (F13); PromptedOutput + retry is the fallback for llama.cpp (F4, F19) | Depends on per-provider `supports_response_schema`; client-side validation only (F11) |
| Fallback across providers | `FallbackModel` built in (F7) | LiteLLM Router/fallbacks exist (not verified this run) |
| Testing | `TestModel` / `FunctionModel` (F7) | Not verified this run |
| Supply-chain risk | No incident found this run. Fast cadence, so pin versions. | **LiteLLM PyPI compromise, March 2026** (F10). Mitigable by pinning and hashes, but a visible reputational point in a portfolio demo. |
| Observability (Logfire / OTel / Langfuse) | Not verified this run (belief: Logfire + OTel native) | Not verified this run (belief: Langfuse callbacks for LiteLLM, LangSmith for LangGraph) |

## Bottom line

- **Pick: Pydantic AI (v2.x, pinned).** It covers all three needs in one library: Pydantic-validated outputs with automatic retry, a lightweight tool agent, and every required provider natively, plus `FallbackModel` and `TestModel` for a CI that needs no API key.
- **Runner-up: LangGraph + LiteLLM.**
- **When the runner-up wins:** the agent grows into a multi-step, stateful or human-in-the-loop workflow with checkpoints or branching, or the demo must showcase a LangChain-ecosystem skill a target employer asks for. In that case use LangGraph with langchain chat models, or with Pydantic AI as the model layer, rather than raw LiteLLM.
- **Strongest argument against the pick:** release churn. There were 8 minor releases in about 3 weeks, a v2 major only 4 months old, and the Python ≥ 3.11 floor moved in 2.55.0. Docs and examples online mix v1 and v2 APIs. Mitigation: pin exactly and keep the upgrade in a lockfile (`uv.lock`).
- **Reversibility hedge:** keep the LLM layer behind a thin internal port, for example `classify_root_cause(...) -> RootCause` and `ask_agent(...)`, with Pydantic schemas defined in the domain layer, not in the framework. Pydantic AI can itself use LiteLLM as a provider (F6), so switching gateways later costs no rewrite. The schemas are plain Pydantic models and carry over to LangGraph.
- **Free-tier caveat for the demo:** Groq's documented limits are about 30 RPM and 1K RPD on gpt-oss models (F12). Gemini's free tier is volatile and not published on the official page (F14, F15). Mistral's figures are unofficial (F16). Default to Groq gpt-oss-120b with Tool Output, use `FallbackModel` toward Gemini/Mistral, and offer a local Ollama option.

## Leads not chased

- Pydantic AI Version Policy page and the v2.0.0b1 breaking-change list.
- Logfire / OpenTelemetry instrumentation docs; Langfuse integrations for Pydantic AI, LiteLLM and LangGraph.
- LangGraph 1.0 release date and its stability promise; LangChain `with_structured_output` behaviour per provider.
- LiteLLM Router fallbacks; LiteLLM's post-incident hardening (Trusted Publishing, attestations).
- OpenAI strict JSON schema, Gemini `responseSchema`/`responseJsonSchema`, and Mistral structured-output docs. LiteLLM only says Gemini 2.0+ uses `responseJsonSchema`.
- Groq free plan vs Developer plan distinction (console page needs login); Groq limits for Llama 3.x models.
- Anthropic strict tool use page; status of llama.cpp issues #11847 and #11988.
- Dependency weight (install size) of each stack.

## Looked for but not found

- **Official** Gemini free-tier RPM/RPD numbers: the page defers to AI Studio (F14).
- **Official** Mistral Experiment plan limits: the docs URL returned 404 and only aggregators were found (F16).
- Groq free-plan numbers on a public page: the table is labeled Developer plan (F12).
- Any security incident affecting Pydantic AI: none surfaced, though no dedicated search was run, so this is not proof of absence.
