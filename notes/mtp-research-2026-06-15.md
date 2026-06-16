# MTP research — resume plan (2026-06-15)

## ⬆️ UPDATE / CORRECTION (2026-06-15, later) — read this first
Verified against the official HF model card + llama.cpp upstream status. Corrects §2b below:
- **The drafter is GOOGLE'S OFFICIAL model: `google/gemma-4-26B-A4B-it-assistant`** (0.4B, **same
  262K vocab** as the 26B-A4B, "exact same quality" = lossless). It is NOT a 3rd-party model — the
  `AtomicChat/...-GGUF` is merely a GGUF *conversion* of Google's official model. So the DRAFTER is
  unambiguously **Gemma-4 Series → MODEL-compliant.** The earlier "gray / 3rd-party" framing was wrong.
- **The fork is an INFERENCE ENGINE, not a model.** The contest rule restricts *models*
  (Gemma-4 / Qwen / BGE-m3 / Qwen-Rerank), not the inference engine. Running official Gemma-4 models on
  a llama.cpp fork does NOT violate the model rule; it is a build-complexity + a strict-judge
  *perception* concern only, resolvable with a clear method writeup.
- **CRUCIAL — there are TWO different MTP shapes; the one we use needs NO FORK:**
  - ✅ **`--spec-type draft-mtp` + a draft-mtp GGUF** (`unsloth/...` → `mtp-gemma-4-26B-A4B-it.gguf`,
    ~441M). This is supported in **UPSTREAM llama.cpp** (PR #23398, merged 2026-06-07) — **NO FORK.**
    This is EXACTLY what `docker/neko-entrypoint.sh` + `scripts/gpu/run_mtp_server.sh` already run, and
    what measured **1.37×** on 2026-06-13 (upstream commit 597b6672). The draft is a Gemma-4 MTP head
    (derived from the official Gemma-4-26B-A4B) → Gemma-4 Series; upstream engine → minimal perception
    risk. **This is the path for Cách 2.**
  - ⚠️ `--spec-type mtp` + the `gemma4_assistant` head (AtomicChat GGUF) needs the `atomic-llama-cpp`
    fork (upstream can't load the arch — #22735). Possibly faster, but forked engine. **NOT used.**
  - (Transformers `assistant_model=` works fork-free but its 26B inference is slower than our llama.cpp
    Q4 base → nets the whole run slower → defeats the Time purpose. Not used.)
- **Net:** **Cách 2 = the no-fork upstream `draft-mtp` + unsloth draft (ALREADY integrated, 1.37×,
  lossless, with a safe fallback to in-process if llama-server is unhealthy).** The ONE remaining
  blocker is the §1 **parity bug** (the `local_server` provider posts to `/v1/chat/completions` →
  server applies its own template → malformed Gemma prompt → 75% answer-fallback). FIX = make the
  `local_server` client POST to the raw `/completion` endpoint with the EXACT in-process Gemma prompt.
  No fork, no exotic arch — just the parity fix + a GPU re-validate + Docker wiring. Time is already
  safe (~1.6 h/2000 q) so the edge is small, but the path is now clean (no fork).

## ✅ PARITY FIX IMPLEMENTED (2026-06-15, offline, no GPU) — solved via Google's official docs
The in-process path uses the GGUF-embedded template (config `local_chat_format=""`), NOT
`format_gemma` (which DROPS system). The exact official Gemma-4 prompt (ai.google.dev/gemma/docs/core/
prompt-structure): no system role → system merged into the user turn with a blank line:
`<start_of_turn>user\n{system}\n\n{user}<end_of_turn>\n<start_of_turn>model\n` (server adds BOS, stop
`<end_of_turn>`). New `src/hackaithon_c/local_server_client.py::LocalServerChatClient` builds that
prompt and POSTs it to the RAW `/completion` endpoint (bypassing the server chat template), with the
GBNF letter grammar + retry; `build_chat_client` now uses it for `local_server` instead of the
OpenAI-chat client. 244/244 tests green; imports stay torch-free.
- **GPU VERIFY PASSED (2026-06-15):** built llama-server (pinned ref 597b6672, upstream draft-mtp, NO
  fork) + main Q4 + unsloth draft, ran the harness via the `local_server` MTP path on N=60 →
  **fallbacks=0** (vs the old ~75% — the /completion parity fix WORKS), all 60 `gemma_self_consistency`,
  **96.7% agreement (58/60) vs the locked 88.34 in-process pred** (the 2 diffs = self-consistency
  sampling noise on borderline items). Wall 205s/60. Speed lever (~1.37×) already measured 2026-06-13.
  Artifacts `Temp/pod_mtp/verify_out/`. → Parity is SOLVED + verified; the no-fork upstream MTP path is
  shippable. Remaining = build + push the MTP Docker image (owner-gated: Docker push + leaderboard).

---


Web research into how llama.cpp + the community handle (a) the **chat-template / accuracy blocker**
and (b) **MTP speculative decoding** for Gemma-4. Pairs with the verdict in
`mtp-packaging-session-2026-06-14.md`: *MTP is lossless; the accuracy loss was the `local_server`
chat path, not MTP.* This doc confirms that with upstream sources and gives the fix.

## 1. The REAL blocker — llama-server `/v1/chat/completions` applies its own template

Confirmed by the upstream discussion (#9741): **you cannot supply your own chat template to
llama-server's `/chat/completions` endpoint** — it applies the GGUF-embedded / built-in template,
which does **not** match our in-process path (`create_chat_completion`, `chat_format="gemma"` +
`merge_system_into_user`). Mismatch → malformed Gemma prompt → model EOS's early → no `ANSWER:` →
high fallback. This is exactly our 75%→52% fallback symptom.

**Fix (community-recommended):** stop using `/v1/chat/completions` for `local_server`. Instead POST
to the raw **`/completion`** endpoint with a **prompt string we build ourselves** that byte-matches
what the in-process Gemma `chat_format` produces (system merged into the user turn, correct
`<start_of_turn>user … <end_of_turn>\n<start_of_turn>model\n` framing). That is the proven 88.55
formatting. → `local_server` then == in-process → fallback back down to ~1.5%.

Implementation sketch (when we resume):
- Add a `use_raw_completion` mode to the OpenAI-compatible client (`nvidia_client.py`) OR a dedicated
  `local_server` client that builds the Gemma prompt + hits `/completion` (fields: `prompt`,
  `n_predict`, `temperature`, `stop`).
- Reuse the EXACT prompt builder the in-process path uses (mirror llama-cpp-python's gemma
  `chat_format`) so there is zero drift.
- Acceptance test: fallback rate on the dev set must match the in-process path (~1.5%), not 52%.

## 2. MTP / speculative decoding for Gemma-4 (the speed feature) — lossless

llama.cpp has native MTP now. Two shapes seen in the wild:
- **Generic speculative**: `--model-draft <draft.gguf> --spec-type draft-mtp --spec-draft-n-max 2-4`.
- **MTP head**: `--spec-type mtp` + a matched assistant ("MTP head") for the target.

**Matched draft for OUR exact model:** `AtomicChat/gemma-4-26B-A4B-it-assistant-GGUF` (~0.4B; Q4_K_M
~310MB) is the assistant/drafter for `google/gemma-4-26B-A4B-it` — "zero quality loss" (the target
verifies every drafted token). Example:
```
llama-server -m gemma-4-26B-A4B-it-Q4_K_M.gguf \
  --mtp-head gemma-4-26B-A4B-it-assistant.Q4_K_M.gguf \
  --spec-type mtp --draft-block-size 3 --draft-max 8 --draft-min 0
```

**⚠️ Big caveat — fork required:** the AtomicChat assistant GGUF uses a custom `gemma4_assistant`
architecture and needs the **`atomic-llama-cpp-turboquant` fork**, NOT upstream llama.cpp (upstream
fails with "unknown architecture"). So shipping it means building the image against that fork →
complicates the portable build + supply-chain. Decide vs a generic draft model on upstream llama.cpp.

**Numbers (Google, Gemma-4):** 2.5–3.1× decode, up to ~5× on math/reasoning; acceptance ≥80% on
structured (code/math/reasoning) output. Our earlier measure was ~1.37× — consistent with a
conservative draft setting; tuning `--draft-max`/`--draft-block-size` should lift it.

## 2b. ⚠️ COMPLIANCE — the MTP assistant is a GRAY AREA for Bảng C rules

Bảng C restricts LLMs to the **Gemma-4 / Qwen3.5≤9B** series. The `gemma-4-26B-A4B-it-assistant`
MTP head is a **separate file**, with a **distinct architecture** (`gemma4_assistant`), that needs a
**non-upstream fork** (atomic-llama-cpp-turboquant), and the GGUF is a **third-party (AtomicChat)
conversion**, not Google's official file.

- **Substance = compliant:** it's Gemma-4's OWN MTP head, and speculative decoding is lossless (the
  Gemma-4 target verifies every token → the answer is exactly Gemma-4's; the draft only accelerates,
  like KV-cache/flash-attn/quant — an inference technique, not a different answering model).
- **Form = risky:** a strict judge glancing at "is this Gemma-4?" sees a 2nd model file + odd arch +
  a forked runtime → could flag it / demand justification. Provenance (3rd-party convert) adds doubt.

**Verdict:** Time is 10pt; Accuracy is 80pt + disqualification risk. NOT worth shipping the
assistant+fork. Either (a) get BTC's explicit OK that spec-decoding draft/MTP-heads count as "using
Gemma-4", or (b) use a **smaller genuine Gemma-4 model** as the draft on **upstream** llama.cpp (no
fork, no exotic arch → unambiguously Gemma-4, lower acceptance). The shipped pure Gemma-4-26B-A4B
portable image stays the safe submission.

## 3. Resume order (do NOT skip step 1)

1. **Accuracy parity first** — switch `local_server` to `/completion` + exact Gemma prompt; prove
   fallback ≈ in-process (~1.5%) and answers match. This is the actual fix; MTP is irrelevant until
   parity holds.
2. **Then add MTP for Time** — but mind §2b (compliance). Preferred path = **(b) a smaller genuine
   Gemma-4 draft on UPSTREAM llama.cpp** (no fork, unambiguously Gemma-4). Only use the
   `gemma-4-26B-A4B-it-assistant` MTP head + atomic fork (best speed) **if BTC confirms** it counts
   as "using Gemma-4". Measure decode speed + verify lossless (answers identical to step-1 baseline).
3. Gate on owner before any GPU spend / image rebuild. Time is only 10pt vs Accuracy 80pt — keep the
   shipped portable image as the safe artifact; MTP is a Time upgrade, not a prerequisite.

## Sources
- llama.cpp server + chat templates: discussion #9741; server README (ggml-org/llama.cpp).
- llama-cpp-python chat_format precedence + Gemma handler: PR #1989 (abetlen/llama-cpp-python).
- MTP in llama.cpp (flags, lossless, benchmarks): knightli.com Gemma-4 assistant-MTP guides;
  datacamp MTP tutorial; AtomicChat/gemma-4-26B-A4B-it-assistant-GGUF (Hugging Face).
