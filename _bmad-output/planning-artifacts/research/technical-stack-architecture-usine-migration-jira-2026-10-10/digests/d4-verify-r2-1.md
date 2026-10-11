# d4-verify-r2-1 : verification L1..L7 (accessed 2026-10-10)

## L1 pydantic-ai versions : VERIFIED (v1.0 date not directly checked)
- PyPI JSON for 2.55.0: wheel uploaded 2026-10-09 19:40:32 UTC (https://pypi.org/pypi/pydantic-ai/2.55.0/json, PyPI). info.version = 2.55.0 on main JSON.
- GitHub releases API: v2.55.0 latest, published_at 2026-10-09T19:20:25Z (https://api.github.com/repos/pydantic/pydantic-ai/releases). Also v1.107.7 on 2026-09-30 (v1 line still maintained in parallel).
- Official changelog lists v2.0.0 dated 2026-06-23 as stable V2.0, after seven betas (b7 = 2026-06-10); V1 "arrived in September 2025" (https://pydantic.dev/docs/ai/changelog/, via search snippet; page not fetched directly). Exact v1.0.0 day not verified.
- Note: "2.55.0 latest" is by 2026-10-09; may be stale within days (fast cadence: 2.52->2.55 in 9 days).

## L2 Pydantic AI outputs / integrations : MOSTLY VERIFIED
- https://pydantic.dev/docs/ai/core-concepts/output/ (Pydantic): Tool Output is default; Native Output uses model's built-in structured output (not all models); Prompted Output injects schema in instructions, least reliable. Retry: ModelRetry in output function/validator; "Each ModelRetry ... consumes one unit of the run's output retry budget", default 1, configurable `Agent(retries={'output': N})` or `ToolOutput(max_retries=N)`. CORRECTION: validation-failure retry exists but default budget is 1.
- Langfuse: https://langfuse.com/integrations/frameworks/pydantic-ai (Langfuse): `Agent.instrument_all()` or `Agent(..., instrument=True)` exports OTel spans to Langfuse; env vars LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL (page documents no OTEL_EXPORTER_* vars). Logfire path not checked.
- UNVERIFIED this run: FallbackModel, TestModel/FunctionModel, provider list (Groq, Anthropic, OpenAI, Mistral, Google, Azure, Ollama, LiteLLM).

## L3 : VERIFIED (versions), VERIFIED (advisory)
- langgraph info.version 1.2.14 (https://pypi.org/pypi/langgraph/json); litellm info.version 1.104.2, not yanked (https://pypi.org/pypi/litellm/json). Upload dates not retrieved.
- Official advisory: https://docs.litellm.ai/blog/security-update-march-2026 (LiteLLM/BerriAI, last updated 2026-03-27, update 03-30): PyPI 1.82.7 and 1.82.8 malicious, live 2026-03-24 from 10:39 UTC ~40 min before PyPI quarantine; exposure window 10:39-16:00 UTC; both removed from PyPI; maintainer PyPI account suspected, possibly linked to Trivy compromise; Docker proxy image, Cloud, <=1.82.6 not affected; clean release v1.83.0 (2026-03-30). 1.82.8 had litellm_init.pth.
- Corroboration (press, via search snippets, not fetched): netenrich.com, truesec.com, CSA research note 2026-03-27; attribution to TeamPCP. Minor discrepancy: 10:39 and 10:52 UTC publish times (press) vs "~40 min" window (advisory).
- Practical: https://pypi.org/pypi/litellm/1.82.8/json returns 404 (consistent with removal).

## L4 Groq : PARTLY OVERTURNED
- https://console.groq.com/docs/rate-limits (Groq): table is the "Developer plan" base limits, NOT free plan; llama-3.3-70b-versatile not listed. Developer plan: gpt-oss-120b, gpt-oss-20b, qwen/qwen3.8-27b each 30 RPM / 1K RPD / 8K TPM / 200K TPD. Free-plan limits only visible in console account page (console.groq.com/settings/limits). Free numbers UNVERIFIED; do not cite the above as free.
- https://console.groq.com/docs/structured-outputs: strict:true supported on openai/gpt-oss-20b, openai/gpt-oss-120b, qwen/qwen3.8-27b (3 models). Quote: "Streaming and tool use are not currently supported with Structured Outputs." VERIFIED.

## L5 Gemini free tier : UNVERIFIED (official numbers)
- https://ai.google.dev/gemini-api/docs/rate-limits shows no per-model numbers; says limits viewable in AI Studio (aistudio.google.com/rate-limit); per project; RPD resets midnight PT. 
- Third-party blogs only (yingtu.ai, laozhang.ai, dev.to; Dec 2025-Jan 2026): Dec 2025 cut, 2.5 Flash RPD ~250 -> ~20; Flash-Lite ~30 RPM / 1,000 RPD; sources conflict, no official changelog found. Treat as unverified.

## L6 Mistral free : VERIFIED (official snippet)
- https://help.mistral.ai/en/articles/225174-what-are-the-limits-of-the-free-tier (Mistral; search snippet, page not fetched): 1 request/s, 500,000 tokens/min, 1 billion tokens/month; for evaluation/prototyping. Free requires data-training opt-in and phone verification (secondary). Per-model vs workspace scoping conflicting between sources; admin console Limits page is authoritative.

## L7 : PARTLY VERIFIED
- Anthropic: https://platform.claude.com/docs/en/build-with-claude/structured-outputs (Anthropic): status GA on Claude API; `output_config.format` = {type:"json_schema", schema}. Unsupported schema features return 400 (NOT silently ignored): recursive schemas, minimum/maximum/multipleOf, minLength/maxLength, minItems>1, additionalProperties != false. SDK helpers may move constraints into descriptions.
- Ollama: https://docs.ollama.com/capabilities/structured-outputs : "Provide a JSON schema to the `format` field." VERIFIED.
- llama.cpp: server README supports `json_schema` (/completion, -j flag) and `response_format` on /v1/chat/completions; README (first 100k chars) does NOT say unsupported keywords are silently ignored; points to tests/test-json-schema-to-grammar.cpp. "Silently ignored" UNVERIFIED.
- OpenAI strict json_schema: not checked.

## New findings
- Groq model list now includes qwen/qwen3.8-27b; Anthropic doc lists claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5 as supported.
- pydantic-ai v1.x line still released alongside 2.x (v1.107.7, 2026-09-30).
- LiteLLM clean release v1.83.0 after incident; pin >=1.83.0 or verified.

## Looked for but not found
- Groq free-plan numbers; llama-3.3-70b limits; official Gemini per-model free numbers and Dec 2025 changelog; PyPI upload dates for langgraph 1.2.14 / litellm 1.104.2 (JSON truncated); exact v1.0.0 date; FallbackModel/TestModel docs; OpenAI strict schema doc; llama.cpp ignored-keyword statement; Logfire OTel doc.
