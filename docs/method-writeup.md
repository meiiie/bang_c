# Neko Core — Method Write-up (HackAIthon 2026, Bảng C)

Status: Method complete; numbers below are measured on the 463-question public set
Last updated: 2026-06-12

> Canonical English technical write-up (the "Idea / method" deliverable). Every accuracy
> number here is **measured**, never invented. Levers that were tried and *rejected* are
> reported with their measured reason — the discipline is as much a part of the method as
> the wins.

## 1. Problem & contract

Bảng C asks for an AI agent that answers multiple-choice questions. The deliverable is a
**self-contained, offline Docker image** that reads `/data/*_test.csv` (or `.json`) and
writes `/output/pred.csv` with exactly two columns `qid,answer` (per-row option letters).
Private scoring runs on **2000 multilingual questions**: Accuracy **80 pts**, inference
time **10 pts**, idea/creativity **10 pts**. Allowed models: **Gemma-4** and
**Qwen3.5 ≤9B** (embed/rerank **BGE-m3 / Qwen-Rerank**).

The runtime ships **Gemma-4 26B-A4B QAT Q4_0 GGUF** on `llama.cpp` — a Mixture-of-Experts
model (~4B active parameters, ~14.4 GB) chosen deliberately over the dense 31B variant
(see §6).

## 2. Design philosophy

Neko Core is a **config-first inference harness**, deliberately small and reproducible.
Four principles drive every decision:

1. **The model reasons; the harness orchestrates and measures.** We do not hard-code
   answers or per-question formulas. We give a strong open model room to reason and we
   measure how much to trust each output.
2. **Anti-overfit, enforced by measurement.** The private set is multilingual and diverse;
   anything tuned to a specific public question or one language is a liability. A lever
   ships only if it *generalises* — proven by an out-of-distribution measurement, not a
   plausible story. New language / question type = a config entry, not a code change.
3. **Calibrated uncertainty.** Confidence is a real observable signal (sample agreement),
   so the harness can *see* where it is likely wrong and spend extra compute only there —
   protecting the 10-pt time score.
4. **A hard runtime/development boundary.** The submitted container is offline and
   self-contained (no web, no external services, no hidden state). All tracing, review,
   and analysis live in development and never ship.

## 3. Architecture

```
/data CSV|JSON
  → loader            (per-row Problem: qid, question, choices; NFC-normalised, BOM-safe)
  → router/classifier (language-agnostic structural signals → strategy)
  → solver            (self-consistency CoT engine; TIR / reading / safety modes routed in)
  → answer normaliser (extracts the option letter, incl. from chain-of-thought)
  → constrained repair (GBNF grammar forces a valid letter if a sample drifts)
  → contract repair   (guarantees pred.csv covers every input qid with a valid letter)
  → exporter          → /output/pred.csv
  → (dev only) trace / review / eval / checkpoint / run-manifest
```

The provider layer hides one `complete()` contract, so the local Gemma GGUF (contest
runtime) and a Qwen3.5 / dev API are interchangeable without touching solver logic. A
policy gate plus agent/tool/command registries enforce that no development-only capability
leaks into the runtime container.

## 4. The accuracy levers (measured)

The public-test leaderboard is the **only** scoreboard we trust. Progression on the
463-question public set:

| Configuration | Public accuracy | Note |
|---|---|---|
| Letter-only baseline (forced single token) | **77.11** | reasoning suppressed |
| **Self-consistency chain-of-thought** | **87.26** | +10.15 pp — the core engine |
| **+ safety-refusal lever** | **88.55** | +1.29 pp, generalising (see below) |

Frontier reference: a hand-solved upper bound on the same 463 reaches **91.79**, and the
remaining gap is dominated by **Vietnamese-2025 administrative facts, local trivia, and a
handful of defective gold keys** (the test's own answer is provably wrong on ≥6/463 —
e.g. a one-gene Punnett square whose gold demands an impossible 1/5). This is why the
honest offline ceiling sits near the high 80s, not 95+: the residual is knowledge a closed
27 GB model simply does not contain, not reasoning it can recover.

**Lever 1 — Let the model reason (chain-of-thought).** The baseline forced letter-only
output, capping accuracy on calculation and multi-step items. A language-neutral reasoning
prompt with letter extraction recovers them: **+10 pp**, the single biggest move.

**Lever 2 — Self-consistency = accuracy *and* a real confidence.** We sample the reasoning,
majority-vote the letter, and set **confidence = agreement fraction**. This both lifts
accuracy and makes risk-review and compute-triage meaningful (calibration replaces the
baseline's hard-coded 0.88 that hid ~57 silent errors).

**Lever 3 — Safety-refusal judgment (+1.29 pp, proven).** A class of questions solicits
*how to commit an illegal/harmful act* (evade a ban, falsify documents, withhold from
authorities, abuse power). The gold answer for these is the option that **refuses**. A
single semantic clause — judge by the *meaning* of the request, never pick a refusal for a
legitimate question — converts these. It is keyword-free and universal, so it transfers to
the multilingual private set; measured +1.29 pp with no observed regression.

**Lever 4 — Gated TIR for the quantitative slice.** ~25–30 % of the test is cross-domain
quantitative (econ/calc/kinetics/stats, heavy in 10-choice items). Behind a numeric
classifier, the solver executes **Python in a sandbox** and self-consistency-votes on the
*setup* (not just the arithmetic) to avoid the "solves the wrong system" trap. Offline-safe;
generalises with the math fraction.

**Lever 5 — Constrained decoding on repair.** If a chain-of-thought sample yields no
parseable letter, the re-ask is issued with a **GBNF grammar admitting exactly the valid
option letters**, so a free-text drift can never fall through to a heuristic guess. The
grammar builder degrades gracefully (unconstrained fallback) if `llama.cpp` lacks grammar
support — it can never break a run.

**Lever 6 — Choice-permutation debiasing.** 29 % of items are 10-choice, where position
bias matters most; cyclic option permutation neutralises it before voting.

## 5. Robustness — the bulletproof contract

The submission is scored on `/output/pred.csv`; the worst failure mode is an **absent or
partial file (zero score)**. Two guarantees make that impossible:

- **Every question is answerable.** A solver exception is caught per-question and replaced
  by a deterministic heuristic fallback — one bad question cannot crash the run.
- **pred.csv is written before anything that can raise.** A *contract-repair* pass rebuilds
  the prediction list to cover **exactly the input qids, in order, each with a letter valid
  for its own problem** (good predictions kept verbatim; missing/out-of-range/duplicate
  filled deterministically). The file is then written *before* validation, which now only
  warns. A single solver gap or an unexpected error can never zero a 2000-question run.

The loader is input-tolerant: BOM-safe UTF-8, NFC diacritic normalisation (decomposed VI
diacritics tokenise differently and silently degrade the model), flexible column names
(`qid/id`, `question/prompt`, `choices/options` or per-letter columns), and a dynamic
option count (no hard-coded A–D). Sampling is deterministic; every run emits a manifest
(config/input hashes, model, strategy, CLI args) and an immutable trace. **211 unit tests
green**, plus dry-run contract checks and a policy audit.

## 6. Anti-overfit discipline — what we *rejected*, and why

Reporting the rejects is the point: each was killed by a measurement, not a hunch.

- **Blanket RAG (BM25 over a VI corpus): rejected.** Measured negative on the real
  distribution (civics −5 pp, quant −7.5 pp where it fired). A closed-book self-contained
  MCQ has no corpus to retrieve from; its realistic reachable slice is ~10–15 %, mostly
  unretrievable-verbatim. Kept OFF.
- **Dense 31B model: rejected for the time score.** Measured **~90 s/question** on an
  A6000 (all 31B parameters active per token) → ~50 hours for the 2000-question private
  set, which forfeits the 10-pt time score. It scored only ~0.7 pp above 26B — inside the
  noise. The 26B MoE (~4B active) is ~6× faster at the same reasoning depth and is the
  shipped contestant.
- **Same-model adjudicator: rejected.** Self-agreement inflates confidence; a *different*
  family is the correct verifier. A Qwen3.5 cross-model challenger is **designed but not
  adopted** — it stays off until an out-of-distribution measurement shows it recovers
  accuracy beyond its time cost. "Measure before adopting" is a hard rule.
- **Per-question formula solvers / VI-specific answer rules: removed.** They contributed
  ~0 on unseen questions and carried mis-fire risk.

## 7. Efficiency (the 10-pt time score)

Inference time is a first-class objective, not an afterthought. The MoE model, agreement-
based compute triage (high-agreement items finish in one cheap pass; only the uncertain
tail escalates), and a tunable reasoning-token budget (the Time↔Accuracy dial) keep the
2000-question run inside budget while spending tokens only where they change the answer.
Checkpointing with `--auto-resume` makes the run restartable without recomputation.

## 8. Honest status

Measured on the public 463: **88.55** (self-consistency CoT + safety lever), up from the
77.11 letter-only baseline; frontier hand-solved ceiling 91.79 with the residual dominated
by VI-knowledge and defective golds. Implemented, unit-tested (211 green), and shipped in
the runtime: the self-consistency engine with agreement calibration, the safety lever,
gated TIR, constrained-decoding repair, choice-permutation debiasing, and the bulletproof
pred.csv contract. Designed but deliberately *not* shipped pending an OOD measurement: the
Qwen cross-model challenger and tiered escalation tuning. No number here is guessed.
