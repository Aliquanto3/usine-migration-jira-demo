# D5: local LLM for 8 GB VRAM (French, JSON schema, tool calling), r1-1

Decision served: pick an open-weight LLM that runs fully on a consumer GPU with 8 GB VRAM (Windows) for French ticket reading and classification, schema-matching JSON and a small read-only tool-calling agent, and choose how to serve it behind an OpenAI-compatible endpoint.
Shape: SELECT. Accessed: 2026-10-10. Budget used: 16 sources, 18 tool calls.

Classes: `vendor-claim` (model card or vendor doc), `primary-doc` (project docs), `practitioner` (issue tracker, blog), `measured` (file sizes listed on the Hub), `estimate` (computed here from architecture figures; not measured).

## Findings

1. **Ministral 3 (3B/8B/14B, "2512") exists.** It is Apache-2.0 and lists French among its languages. The 8B is "8.4B LM + 0.4B vision encoder" with a 256k context. The card claims "best-in-class agentic capabilities with native function calling and JSON outputting" and recommends a temperature below 0.1 and a small tool set.
   - Source: https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512 (Mistral AI, model family "2512" = Dec 2025, card updated 2026-07-15)
   - Confidence: high (existence, licence); medium (capability claims). Class: vendor-claim.
   - Freshness: about 10 months old, which is older than the 3-month window. Flagged.
2. **Ministral 3 8B base scores (vendor).** Multilingual MMLU is 0.706, against 0.700 for Qwen3 8B Base. On the instruct side it scores WildBench 66.8 and Arena Hard 0.509, against 66.3 and 0.528 for Qwen3-VL-8B. The card gives no BFCL figure and no French-specific score.
   - Source: same card as finding 1.
   - Confidence: medium. Class: vendor-claim.
3. **Official Ministral 3 8B GGUF sizes.** Q4_K_M is 5.20 GB, Q5_K_M is 6.06 GB and Q8_0 is 9.03 GB. The vision projector (mmproj) is a separate 0.86 GB file and is not needed for text.
   - Source: https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF (Mistral AI, updated 2026-01-15)
   - Confidence: high. Class: measured.
4. **Qwen3.5-9B exists.** It is Apache-2.0, released around Feb–Mar 2026, with 262k native context. It uses a hybrid layout of 8 × (3 Gated DeltaNet + 1 Gated Attention) blocks, and its attention layers have 4 KV heads with head dim 256. Thinking is on by default. Thinking is turned off with `chat_template_kwargs: {"enable_thinking": false}`, and the `/think` and `/nothink` soft switches are not supported.
   - Source: https://huggingface.co/Qwen/Qwen3.5-9B (Qwen / Alibaba, card updated 2026-03-02)
   - Confidence: high. Class: vendor-claim.
5. **Qwen3.5-9B vendor scores.** BFCL-V4 66.1 (the 4B scores 50.3), TAU2 79.1, IFEval 91.5, MMMLU 81.2, MMLU-ProX 76.3, WMT24++ 72.6. Tool calling uses the `qwen3_coder` (XML) parser in vLLM.
   - Source: same card as finding 4.
   - Confidence: medium. Class: vendor-claim.
6. **Qwen3.5-9B GGUF sizes (unsloth).** Q4_K_M is 5.68 GB, UD-Q4_K_XL is 5.97 GB and Q5_K_M is 6.58 GB.
   - Source: https://huggingface.co/unsloth/Qwen3.5-9B-GGUF (Unsloth, 2026-03-02)
   - Confidence: high. Class: measured.
7. **Qwen3.5 tool calling is broken in llama.cpp when thinking is on.** The model writes tool calls as XML inside the thinking block and the turn ends with `finish_reason: stop`, so no tool call is parsed. Turning thinking off (`enable_thinking:false`) fixes it. The issue was reproduced on Qwen3.5-9B UD-Q4_K_XL and on Qwen3.6 variants. It is still open, with a confirming comment on 2026-09-07. A maintainer says the grammar trigger is separate from the reasoning parser.
   - Source: https://github.com/ggml-org/llama.cpp/issues/20837 (GitHub / llama.cpp, 2026-03-21, activity to 2026-09-07)
   - Confidence: high. Class: practitioner.
8. **Qwen3.5 tool calling is also unreliable in Ollama.** Users report that its renderer and parser use Hermes-style JSON while the model was trained on Qwen3-Coder XML. They also report that the penalty sampling parameters are ignored by the Go runner. Some PRs (#14603, #15224) fixed parts of it. The issue is still open with reports in Aug–Sep 2026, and a maintainer disputes the "completely non-functional" wording.
   - Source: https://github.com/ollama/ollama/issues/14493 (GitHub / Ollama, 2026-02-27 to 2026-09)
   - Confidence: medium-high. Class: practitioner.
   - Two-source class: together with finding 7, this gives two independent sources for Qwen3.5 tool-calling fragility.
9. **Gemma 4 (E2B, E4B, 12B, 26B-A4B, 31B) is Apache-2.0.** The card links the "gemma_4_license" page but labels it Apache 2.0. It supports native function calling, a native system role and configurable thinking. It claims 35+ supported languages, with pre-training on 140+.
   - Vendor scores: 12B gets Tau2 69.0% and MMMLU 83.4%. E4B gets Tau2 42.2% and MMMLU 76.6%.
   - Source: https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf (Google DeepMind, updated 2026-07-17)
   - Confidence: high (licence label); medium (scores). Class: vendor-claim.
10. **Gemma 4 official QAT GGUF sizes.** 12B Q4_0 is 6.98 GB (plus a 0.18 GB mmproj). E4B Q4_0 is 5.15 GB (plus a 0.99 GB mmproj).
    - Source: https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf and https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf (Google, 2026-07-17)
    - Confidence: high. Class: measured.
11. **Gemma 4 tool calls work in llama.cpp with a recent build and `--jinja`, with reported bugs.** One guide reports that basic tool calls worked cleanly. Another April write-up reports "real bugs", especially with tool calling and on Apple Silicon.
    - Source: https://codex.danielvaughan.com/2026/04/10/gemma-4-local-model-codex-cli-complete-setup-guide/ (Daniel Vaughan blog, 2026-04-10)
    - Confidence: low-medium. Class: practitioner.
    - Freshness: about 6 months old. Flagged.
12. **IBM Granite 4.2 8B was released on 2026-08-25.** It is Apache-2.0, dense, with GQA (40 layers, 8 KV heads, head dim 128). It has thinking on by default with a non-thinking mode, and French is a tested language.
    - Vendor scores: BFCL v4 52.39, τ³-bench 58.06. RL was trained on structured-output environments.
    - Source: https://huggingface.co/ibm-granite/granite-4.2-8b (IBM, 2026-09-04)
    - Confidence: high (facts); medium (scores). Class: vendor-claim.
13. **Granite 4.2 8B official GGUF sizes.** Q4_K_M is 5.35 GB and Q5_K_M is 6.25 GB. The repo ships a `granite_thinking_parser.py`.
    - Source: https://huggingface.co/ibm-granite/granite-4.2-8b-GGUF (IBM, 2026-09-02)
    - Confidence: high. Class: measured.
14. **llama.cpp function-calling doc: native handlers and fallback.** The doc lists native handlers for Llama 3.x, Hermes, Qwen 2.5, Mistral Nemo, Functionary, Command R7B and GPT-OSS. Templates it does not recognise fall back to "Generic" (Ministral-3b is listed as Generic). The doc warns that "extreme KV quantizations (e.g. `-ctk q4_0`) … can substantially degrade the model's tool calling performance". Parallel tool calls must be turned on with `parallel_tool_calls: true`.
    - Source: https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md (ggml-org, undated)
    - Confidence: medium. Class: primary-doc.
    - Freshness: the doc looks stale (its example dates to 2024), so the handler list may lag the code.
15. **`llama-server` options.** It supports `response_format` with `json_object` and `json_schema` (grammar-based sampling), plus raw `json_schema` and `grammar` request parameters. `--jinja` is now enabled by default.
    - Reasoning controls: `--reasoning on|off|auto`, `--reasoning-budget`, `reasoning_effort: none` and `chat_template_kwargs`.
    - KV cache type is set with `-ctk`/`-ctv`, and flash attention with `-fa auto`.
    - The README does not say whether schema-constrained output and tools can be combined.
    - Source: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md (ggml-org, undated, current master)
    - Confidence: high. Class: primary-doc.
16. **Ollama structured outputs.** The JSON schema goes in the `format` field, and the OpenAI-compatible API accepts `response_format`. The docs do not say whether decoding is constrained or how this interacts with thinking or tools. They recommend temperature 0.
    - Source: https://docs.ollama.com/capabilities/structured-outputs (Ollama, undated)
    - Confidence: high. Class: primary-doc.
17. **Ollama issue: tools are ignored when `response_format` is set on self-hosted Ollama.** Issue #13750 was opened on 2026-01-16 and is still open.
    - Ollama's Ministral-specific tool bugs were all closed by Jan 2026: nested objects returned HTTP 500 (#13705), multiple tool calls (#13334), and more than 2 tools (#13328).
    - Source: https://github.com/ollama/ollama/issues?q=ministral-3+tool (GitHub / Ollama, accessed 2026-10-10)
    - Confidence: medium (titles and states only). Class: practitioner.
18. **Ollama library page for `ministral-3`.** It is tagged tools and vision, 8b is 6.0 GB (likely includes vision), 256K context, and it needs Ollama 0.13.1 or later.
    - Source: https://ollama.com/library/ministral-3 (Ollama, updated about 10 months ago)
    - Confidence: high. Class: primary-doc.
19. **KV cache at 16k context (estimate from architecture figures).**
    - Qwen3.5-9B: only 8 of 32 layers keep a KV cache (4 KV heads × 256 dim), about 32 KB/token in f16, about 0.5 GB. DeltaNet state is small and fixed.
    - Granite 4.2 8B: 40 layers × 8 × 128, about 160 KB/token in f16, about 2.6 GB, or about 1.3 GB with q8_0 KV.
    - Ministral 3 8B: the card does not state its layer and KV-head counts. A typical 8B GQA layout would give about 2–2.5 GB in f16, or about 1.1–1.3 GB with q8_0 KV (unverified).
    - Gemma 4 12B: sliding-window layers keep KV small, but the 6.98 GB of weights leave about 1 GB for KV, compute buffers and the Windows desktop on an 8 GB card. That is not practical with full offload.
    - Confidence: medium (Qwen, Granite); low (Ministral). Class: estimate.

## Finalists

| Model | Params | Licence | Q4 GGUF size | French | Tools | JSON | Refs |
|---|---|---|---|---|---|---|---|
| **Ministral 3 8B Instruct 2512** | 8.4B + 0.4B vision | Apache-2.0 | 5.20 GB Q4_K_M (official) | French vendor; fr listed; M-MMLU 0.706 (vendor); no French benchmark found | Native function calling (vendor). Ollama parser bugs closed by Jan 2026. llama.cpp: no native handler documented, generic fallback | "JSON outputting" (vendor); grammar constraint via server | 1, 2, 3, 14, 17, 18 |
| **Qwen3.5-9B** | 9B (+ vision) | Apache-2.0 | 5.68 GB Q4_K_M (unsloth) | 201 languages; MMMLU 81.2, WMT24++ 72.6 (vendor) | BFCL-V4 66.1 (vendor, best here), but **open bugs in llama.cpp and Ollama** with thinking on; fix is to turn thinking off | IFEval 91.5 (vendor) | 4–8 |
| Granite 4.2 8B | 8B dense | Apache-2.0 | 5.35 GB Q4_K_M (official) | fr tested (vendor) | BFCL v4 52.4 (vendor); thinking by default; released 6 weeks ago, so little field evidence | RL on structured output (vendor) | 12, 13 |
| Gemma 4 E4B | 4.5B effective (8B with embeddings) | Apache-2.0 | 5.15 GB Q4_0 QAT | MMMLU 76.6 (vendor) | Native function calling; Tau2 42.2 (weak) | — | 9, 10, 11 |
| (Gemma 4 12B: excluded) | 11.95B | Apache-2.0 | 6.98 GB Q4_0 | MMMLU 83.4 | Tau2 69.0 | — | Does not fit 8 GB with useful context |

## Bottom line

**Pick: Ministral 3 8B Instruct 2512, Q4_K_M (5.2 GB), text only (skip the mmproj).**
- Apache-2.0, from a French vendor, with native function calling and JSON output claimed on the card.
- It is a non-thinking instruct model, so it avoids the thinking/tool-call interaction bug that affects Qwen3.5 and probably Granite 4.2.
- Ollama's Ministral tool-call bugs are closed.
- Weakness: no independent French or BFCL number was found (vendor claims only). The data is about 10 months old.

**Runner-up: Qwen3.5-9B, Q4_K_M (5.68 GB), run with `enable_thinking:false`.**
- It has the best vendor numbers here (BFCL-V4 66.1, multilingual) and the smallest KV cache, about 0.5 GB at 16k.
- Two independent trackers (llama.cpp #20837, Ollama #14493) show tool calling still broken with thinking on as of Sep 2026. It is only acceptable with thinking forced off and a smoke test.
- **Choose it over Ministral if a 20-ticket French A/B on our own data shows better root-cause classification.** That A/B is the cheap decider.

**Serving: llama.cpp `llama-server` (Windows CUDA build) as primary.**
- Example command: `llama-server -m Ministral-3-8B-Instruct-2512-Q4_K_M.gguf -ngl 99 -c 16384 -fa on -ctk q8_0 -ctv q8_0 --jinja --temp 0.1 --port 8080`
- For Qwen, add `--reasoning off` or per-request `chat_template_kwargs:{"enable_thinking":false}`.
- Use `response_format: {type:"json_schema", ...}` for classification and comment drafting. It is grammar-constrained and documented.
- Make tool-calling turns separate requests **without** `response_format`, because combining them is undocumented in llama.cpp and broken in self-hosted Ollama (#13750).
- Do not quantize the KV cache below q8_0: the llama.cpp doc warns that q4_0 KV degrades tool calls.

**Ollama: acceptable fallback** (simpler on Windows, `/v1` endpoint, `format` schema). It has a dedicated Ministral parser with its bugs fixed. Avoid it for Qwen3.5 tools, and do not combine tools with `response_format`.

**Risks:**
- llama.cpp may route Ministral 3 through the generic tool-call path (the doc lists Ministral-3b as "Generic"). Verify with a 3-tool smoke test, or use Ollama, before relying on it.
- KV fit for Ministral at 16k on 8 GB is an estimate. Check the VRAM it actually uses (nvidia-smi) and fall back to `-c 8192` if needed.
- All quality claims are vendor claims.

## Leads not chased
- The llama.cpp `common/chat.cpp` history, to see whether a native Ministral-3 / Mistral-3 `[TOOL_CALLS]` handler exists now (doc vs code drift).
- llama.cpp PR #24202 and #20424 (possible Qwen3.5 reasoning/tool-call fix).
- Ministral 3 config.json (layers and KV heads) for an exact KV estimate.
- Qwen3.6 small sizes (mentioned in #20837 comments). Their existence and sizes were not verified.
- The Ministral 3 paper (arXiv 2601.08584) for function-calling evals.
- Gemma 4 4-bit tool-calling reliability on Windows CUDA. Granite 4.2 field reports.
- Phi-4-mini and Llama 3.x 8B were not screened; both are older generations and likely to be outclassed.

## Looked for but not found
- An independent French-language benchmark comparing these small models.
- A BFCL leaderboard entry for Ministral 3 8B (the card gives none).
- An explicit statement that Ollama's `format` uses constrained decoding (the docs are silent).
- Documentation on combining `response_format` with `tools` in llama-server.
- r/LocalLLaMA retrospective threads (search returned blogs instead).
