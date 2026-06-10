# Neko Core — Method Write-up (HackAIthon 2026, Bảng C)

Status: DRAFT (method/strategy complete; final benchmark numbers pending real-model runs)
Last updated: 2026-06-10

> This is the canonical English technical write-up. A Vietnamese adaptation should be
> produced for the actual contest submission ("Tài liệu thuyết minh phương pháp"). No
> accuracy number here is invented — measured numbers are labelled as such, and items
> awaiting a real-model run are labelled "pending".

## 1. Problem & contract

Bảng C asks for an AI agent that answers multiple-choice questions. The deliverable is a
**self-contained Docker image** that reads `/data/public_test.csv` or
`/data/private_test.csv` and writes `/output/pred.csv` with two columns `qid,answer`
(per-row option letters). Scoring on a **2000-question, multilingual** private test:
Accuracy **80 pts**, inference time **10 pts**, idea/creativity **10 pts**. Allowed models
are **Gemma-4** and **Qwen3.5 ≤9B** (embed/rerank **BGE-m3 / Qwen-Rerank**).

## 2. Design philosophy

Neko Core is a **config-first inference harness**, deliberately small and reproducible.
Four principles drive every decision:

1. **The model reasons; the harness orchestrates and measures.** We do not encode answers
   or hand-written formulas; we give a strong open model (Gemma-4 26B) room to reason and
   we measure how confident we should be in its output.
2. **Anti-overfit.** The 2000-question private set is multilingual and diverse. Anything
   tuned to a specific public question or to one language is a liability, so it is removed
   or made general and config-driven. New language or question type = a config entry, not
   a code change.
3. **Calibrated uncertainty.** We replace ad-hoc confidence with a real, observable signal
   (sample agreement), so the harness can *see* where it is likely wrong and spend extra
   compute only there — protecting the time score.
4. **A hard runtime/development boundary.** The submitted container is offline and
   self-contained (no web, no external services, no hidden state). All experimentation,
   tracing, and analysis happen in development and never ship.

## 3. Architecture

A small, layered pipeline (config in `configs/default.json`):

```
/data CSV|JSON
  → loader            (per-row Problem: qid, question, choices)
  → router/classifier (language-agnostic structural signals)
  → solver            (reasoning + self-consistency; legacy strategies retained)
  → answer normaliser (extracts the option letter, incl. from chain-of-thought)
  → calibration       (confidence = sample-agreement fraction)
  → exporter          → /output/pred.csv
  → (dev only) trace / review / eval / checkpoint / run-manifest
```

Provider layer is abstracted behind one `complete()` contract, so Gemma-4 (local
`llama.cpp` GGUF, the contest runtime) and Qwen3.5 / a dev API are interchangeable without
touching solver logic. A policy gate plus agent/tool/command registries enforce that no
development-only capability can leak into the runtime container.

## 4. Optimization strategy (the accuracy & efficiency levers)

The starting baseline scored **85.53** on the 463-question public test (a measured
leaderboard number). Diagnosing it on the real run traces showed the score was held up by
**Vietnamese-specific heuristics and public-test-specific adjudicators that will not
transfer**, and — critically — that **confidence was hard-coded**: 79.5% of answers sat at
≥0.88 while ~67/463 were wrong, i.e. ~57 *silent* errors the harness could not see. Our
strategy targets exactly these recoverable failure classes:

- **Let the model reason (chain-of-thought).** The baseline forced letter-only output
  ("no explanation", ~96 output tokens), which caps accuracy on calculation and multi-step
  items. We use a language-neutral reasoning prompt and extract the final letter from the
  reasoned answer. *(Implemented: `self_consistency` strategy + reasoning prompt.)*
- **Self-consistency = accuracy + a real confidence.** We sample the reasoning *k* times
  and take the majority vote; **confidence is the agreement fraction** (unanimous → 1.0,
  split → lower). This both improves accuracy (majority voting) and makes risk-review and
  compute-triage meaningful. *(Implemented: `calibration.py`.)*
- **Independent cross-model verification.** When agreement is low, a *different* allowed
  model (Qwen3.5-8B) adjudicates — breaking the same-model self-confirmation bias that
  inflated the baseline's confidence. *(Designed; pending real-model validation.)*
- **Tiered, budget-aware compute.** High-agreement items finish in one cheap pass; only the
  uncertain tail escalates (more samples / cross-model). This keeps the 10-pt inference-
  time score reasonable while spending tokens where they change the answer. *(Designed.)*
- **Language-agnostic routing.** Routing relies on script-independent structural signals
  (number of choices, genuine arithmetic signals, context length). For example, the
  calculation route now requires a *real* computation signal (an operator between numbers,
  a number with a unit, two or more numbers, or a quantitative phrase) rather than a topic
  word plus an incidental digit — so "what is the chemical formula for water?" is no longer
  mis-routed as arithmetic. *(Implemented.)* Vietnamese diacritics are preserved (they are
  meaning-bearing); we do not depend on lossy keyword stripping.
- **Remove overfit.** The bespoke per-question formula solvers and domain answer-rules are
  scheduled for removal once the reasoning path is shown to recover those points — they
  contribute ~0 on unseen questions and carry mis-fire risk. *(Pending sign-off + validation.)*

## 5. Runtime & reproducibility

The contest runtime is **Gemma 4 26B A4B QAT Q4_0 GGUF** running locally via `llama.cpp`,
packaged into a self-contained Docker image (no API key needed at scoring). Sampling is
deterministic (temperature 0). Every run emits a manifest (config/input hashes, model,
strategy, CLI args) and an immutable trace, and the output is validated against the exact
`qid,answer` contract before writing `pred.csv`. The harness ships with a unit-test suite
(currently 98 tests green) plus dry-run contract checks and a policy audit.

## 6. Honest status

Measured: baseline **85.53** (public, 463). Implemented & unit-tested (98 tests green):
the safety-net gold suite, the reasoning + self-consistency strategy with agreement-based
calibration, and the language-agnostic calculation-routing fix. **Pending a real-model
run** (needs the allowed model in the dev/build environment): the accuracy and tokens/sec
measurements that quantify the improvement, the cross-model verifier, tiered compute,
removal of the overfit adjudicators, and the final Docker rebuild. These numbers will be
filled in here as they are measured — none are guessed.
