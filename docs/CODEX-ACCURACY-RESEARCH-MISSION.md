# Codex Accuracy Research Mission — Neko Core (HackAIthon 2026 Bảng C)

Status: ACTIVE operating brief for the autonomous research agent (Codex / GPT-5.5).
Created: 2026-06-13. Author: Claude (handoff while at session limit).

> Owner intent (VI): "Nghiên cứu LIÊN TỤC các phương pháp / kiến trúc / cách suy luận để
> nâng accuracy cho vòng 2, suy nghĩ sâu và tiến hành — NHƯNG tuyệt đối không chắp vá /
> hard-code phá hỏng hệ thống trên 2000 câu private. Mỗi cải tiến phải đo thật và nộp
> vòng-1 để xác nhận điểm có tăng không."

Read this together with `AGENTS.md`, `notes/RESUME-HERE.md`, and `notes/lessons.md`. This
document does not replace them; it defines the **mission, the iron rules, the pruned search
space, the research agenda, and the operating loop** so you can work continuously without
drifting into the failure mode that already cost us once.

---

## 0. Prime directive & success criteria

**Goal:** raise *true, generalizable* accuracy on the 2000-question multilingual private test
beyond the current `self_consistency` ≈ 88.55 — without overfitting the 463 public questions.

**Success = a lever that satisfies ALL of:**
1. Implemented behind a config flag, OFF by default, with a verification story (unit test +
   dry-run contract check).
2. Wins on a **held-out** dev set (NOT the public 463) **per bucket** (factual / quantitative /
   reading) with **no overall regression**, measured on a real GPU run.
3. Then **confirmed by a round-1 leaderboard submission** (score goes UP). Round-1 is
   accuracy-only and is our only ground-truth signal for whether a change helps round-2.
4. Generalizes by construction (see §1, the overfit test) — works across languages and buckets,
   not by matching known items.

**A negative, measured result is a SUCCESS too** — it prunes the search space and is recorded.
Unmeasured optimism is failure. Proxy-only deltas are NOT proof (see §1).

---

## 1. The iron rules (anti-overfit framework — this is non-negotiable)

We already shipped, measured, and **removed** a patchwork of public-463-fitted rules
(`adjudicated_self_consistency`, bespoke principle/calculation hard-codes). They looked good on
a proxy (+6) and were a liability on the private set. **Do not recreate that failure.**

### The overfit test — apply it to EVERY change before writing code
A lever is **OVERFIT (forbidden)** if ANY of these is true:
- Its existence, its trigger, or its parameters **would be different if you had never seen the
  public-463 questions or answers.** (If you picked a rule *because* it fixes specific public
  items → overfit.)
- It fires on a **match to a known item / qid / answer key / leaderboard observation**, rather
  than on a **semantic or structural property of the input** that holds for unseen items.
- It helps one language (e.g. Vietnamese) or one public slice but cannot be argued to help the
  multilingual private distribution.
- Its only evidence is a **proxy pseudo-reference** (e.g. comparing to a stored Claude/other
  prediction file) — that is a selection signal, never proof of grader accuracy.

A lever is **ALLOWED** if it is a **generic mechanism** (a decoding method, a scoring method, a
prompt architecture, a calibration signal, an allowed retrieval/ensemble) whose behavior is
derived from the input's structure/semantics and would be written identically with zero
knowledge of the public answers.

### Hard constraints (from AGENTS.md + contest rules)
- Offline final Docker: reads `/data`, writes `/output/pred.csv` (`qid,answer`, per-row letters
  A–D, never hard-coded). No internet, browsers, DB, subagents, or hidden state at inference.
- Allowed models ONLY: **Gemma-4 family** and **Qwen3.5 ≤ 9B**; embedders **BGE-m3 /
  Qwen-Rerank**. Runtime contestant = `Gemma-4-26B-A4B QAT Q4_0 GGUF`.
- Do NOT assume the private language is Vietnamese (English / French / Spanish / mixed / VN).
- Config-first: thresholds/markers/defaults live in `configs/default.json` /
  `runtime.profiles`, not in solver branches. No god files; small modular contracts.
- Default contest path stays `self_consistency` until a lever is GPU-measured AND generalizes.
- karpathy-guidelines: think before coding (state assumptions, surface trade-offs), simplicity
  (minimum code, nothing speculative), surgical changes (touch only what the task needs, match
  style), goal-driven (every change has a verification story).
- Honesty: report real measured numbers; mark anything unmeasured as unmeasured.
- PAUSE for owner sign-off before: GPU/RunPod spend, leaderboard submission, publishing or
  overwriting the Docker image. Never commit secrets/.env/outputs/answer files/model weights.

---

## 2. Current state (what is locked — do not relitigate)

- Contestant: `workflow=self_consistency`, single CoT (k=1), `reasoning_max_tokens=2048`,
  safety-refusal lever OFF, low temperature. Public-463 = **88.55** (already submitted; qualifies).
- Bulletproof pred.csv contract shipped (`repair_predictions_for_contract`, write-before-validate)
  — a solver gap can never zero the run. 221 tests green.
- MTP (Multi-Token Prediction) integrated as the **round-2 Time lever** (≈1.37× measured), with a
  safe fallback to in-process `local_llamacpp` (`docker/neko-entrypoint.sh`,
  `Dockerfile.gemma-mtp`). MTP is **lossless / accuracy-neutral** — it is NOT an accuracy lever.
- The overfit hard-codes were removed; `PRINCIPLE_RULES`/`CALCULATION_DECISION_RULES` are empty
  guarded tuples. Keep them empty.

---

## 3. DEAD — measured, do NOT re-spend (the pruned search space)

Re-proposing any of these without a *materially different* mechanism is wasted GPU time:

- **TIR / router** (Python tool execution, quantitative→tool): −9.29pp on the real 463 (false-
  flipped 47 correct to recover 4). `notes/router-tir-measured-2026-06-13.md`.
- **maj@k / self-consistency k>1 / diverse voting:** WASH. Gemma's errors are *systematic* —
  diverse samples agree on the SAME wrong answer (FPT n=120/bucket: 89.7 vs 90.0).
- **Higher-bit quant (Q6_K / Q8_0) and UD-Q4_K_XL swap:** tied-to-worse than the shipped QAT
  Q4_0 at 2× time/VRAM. Accuracy headroom is NOT in precision (our Q4_0 is QAT, not post-train).
- **Dense 31B:** ~+2pp proxy at ~90s/q (~50h on 2000q) → forfeits Time. Rejected.
- **few-shot (blanket), tiered (blanket):** flat / 3× slower no gain (n=150 noise).
- **Qwen3.5-9B standalone:** 84.9% proxy, worse than Gemma (weak at math especially).
- **letter-only / "no explanation" prompts:** HURT reasoning items.
- **self-verification prompting** (−1..−17pp) and **elimination prompting** (−5..−14pp): negative.
- **higher reasoning_max_tokens (3072/4096+):** flat (MoE early-stops). Keep 2048.
- **adjudicated_self_consistency / bespoke public-463 rules:** overfit, proxy-only, REMOVED.

Note: **reading-grounding (LEVEL 2)** and **legal-RAG (LEVEL 3)** are BUILT, gated OFF, and
**not yet GPU-measured** — they are candidates (§4.6), not dead.

---

## 4. Research agenda — untried, plausibly-generalizable candidates

These are **seed hypotheses, ranked by my honest expected value — NOT assumptions.** Research
each with current (2024–2026) literature first, then implement behind a flag and MEASURE. Also
survey for techniques NOT listed here and add them to the backlog. For each candidate the
question to answer is always: *does it generalize (§1), is it offline-feasible, and does it beat
self_consistency per bucket on a held-out set?*

### 4.1 Logprob / cloze MCQ scoring + length/PMI normalization  — HIGH
Instead of (or after) generating a CoT and parsing a letter, compute the model's log-likelihood
of each option string and argmax, with **length or PMI / domain-conditional normalization** to
fix surface-form competition. Generic, language-agnostic, deterministic. Likely helps factual /
short items; may underperform CoT on multi-step quant → consider a **hybrid** (CoT for quant,
normalized cloze for factual) decided by a *generic* signal, never by item identity. Needs
per-token logits from llama.cpp (available). Measure cloze vs generate vs hybrid per bucket.

### 4.2 Factuality-targeted decoding (DoLa / contrastive decoding)  — MEDIUM
DoLa (ICLR'24) contrasts late-vs-early layer logits to amplify factual tokens; contrastive
decoding similar. Model-internal, generic. Research llama.cpp support FIRST (may not expose layer
logits) — if unavailable offline, mark infeasible and move on. Expected: small factual gain.

### 4.3 Translate-to-English pivot for non-English items  — MEDIUM/HIGH (multilingual is the real shift)
The private set is multilingual but our 88.55 was measured on the VN 463. Gemma is strongest in
English. Detect language; for non-English items that don't hinge on source-language nuance,
translate question+options to English with the SAME model, answer, map the letter back. Generic
(triggered by detected language, not item identity). Risk: translation errors on technical/quant
and on language-specific items (idioms, VN-law) → must measure per language and gate by type.
Build a multilingual dev set (translated MMLU / multilingual exam MCQ) to measure honestly.

### 4.4 Cross-model tie-break: Gemma + Qwen3.5≤9B on low-agreement items  — MEDIUM
Unlike maj@k (same model, shared systematic errors), a *different* model has *independent*
errors. Run Gemma default; for low-confidence items only, consult Qwen and combine via
logprob-weighted / disagreement-aware selection. Qwen is weak at math → restrict to factual.
Generic (gated by a confidence signal). Measure on the factual bucket only.

### 4.5 Confidence-aware test-time routing (entropy / logprob-margin)  — MEDIUM
A generic per-item confidence signal (answer-distribution entropy or logprob margin) that
escalates ONLY low-confidence items to a more expensive path (more reasoning / cloze / Qwen
tie-break). The signal is generic, not item-fitted. This is the framework that makes 4.1/4.4
cheap. Needs a working escalation path to be worth measuring.

### 4.6 Legal/admin targeted RAG (LEVEL 3, built+gated) and reading-grounding (LEVEL 2)  — MEDIUM/LOW
Already implemented, OFF by default, never GPU-measured. RAG is gated to the ~10–15% legal/admin
factual slice via a semantic gate (BM25 + BGE-m3 over a bundled general-law corpus — corpus is
law text, not public answers, so it is not overfit). Reading-grounding is the passage analog.
The GPU battery is already staged in `scripts/gpu/` (quant→router, reading→forced reading,
civics→forced rag, paired scoring on `data/devsets/`). Measure per bucket; promote only on a
clean generalizing win.

### 4.7 Generic answer-verification re-read (NOT self-critique)  — LOW
A topic-agnostic final check: "does the chosen letter actually answer what the question asks?"
to catch mis-reads / negation flips. Must be a generic re-read, not a "critique/verify" loop
(those measured negative). Cheap; measure for regression before trusting.

> When you exhaust 4.1–4.7, the honest conclusion may be that 88.55 is the generalizable ceiling
> and the remaining marginal upside is run-to-run variance (~±2–3pp). If so, SAY SO, stop
> spending on accuracy, and shift effort to the round-2 Time/Idea story (MTP + writeup). That is
> a valid, honest end state.

---

## 5. The measurement loop (operating cadence — run this per candidate)

For each backlog candidate, top of the ranked list first:

1. **Research** the technique (2024–2026 sources): does it apply to offline small-model
   multilingual MCQ? Does it generalize (§1)? Note expected effect + failure modes.
2. **Design** the smallest config-gated implementation (a module + a flag, OFF by default).
   State assumptions and trade-offs before coding (karpathy §1).
3. **Implement + verify locally:** unit tests, `python -m unittest discover -s tests -v`,
   `compileall`, dry-run contract check, `--policy`. Keep the default path UNCHANGED.
4. **Held-out dev measurement (GPU, owner-approved spend):** A/B vs `self_consistency` baseline
   **per bucket** on a dev set that is NOT the public 463 (ViGEText / ViMMRC / multilingual
   exam MCQ). Paired scoring, no-regression gate. Use the dev-workflow gate
   (`--allow-development-workflow`) so unmeasured candidates never touch the contest path.
5. **Decide:** generalizing win per bucket + no overall regression? → propose a round-1
   submission to the owner. Negative/flat? → record it as dead (§3 grows) and move to the next
   candidate. Never promote on a proxy or on vibes.
6. **Confirm (owner-gated):** submit round-1; if the leaderboard score rises, promote the lever
   to the contest default (still config-flagged). If it doesn't rise, revert to OFF and record.
7. **Document** every outcome: a dated `notes/<topic>.md` with file:line evidence + a durable
   line in `notes/lessons.md` + update `notes/RESUME-HERE.md` state. Positive AND negative.

GPU/orchestration hygiene (from `notes/lessons.md`): community pods have old CPUs → prebuilt
llama-cpp wheels SIGILL → source-build; always `export HACKC_PROVIDER/HACKC_LOCAL_MODEL_PATH/
HACKC_LLAMACPP_N_CTX/N_GPU_LAYERS`; write .sh → scp → `tr -d '\r'` → bash; cap `cmake -j` on
low-RAM pods; VERIFY a launched run before relaunching (double-load OOM); `podTerminate` after
pulling results.

---

## 6. Continuous-work protocol & stop conditions

- Maintain a **ranked research backlog** (start with §4). Work ONE candidate at a time through
  the §5 loop. Do not block on a single idea — if it stalls or dies, record and advance.
- Prefer a **measured negative** over an **unmeasured positive**. The point of working
  continuously is to *retire* candidates with evidence, not to accumulate untested cleverness.
- Re-survey 2024–2026 SOTA periodically and append new candidates to the backlog.
- **Escalate to the owner only at the two gates** (GPU spend, leaderboard submission) and when a
  candidate is ready to promote. Otherwise keep researching/implementing/measuring.
- **Stop conditions:** (a) a generalizing lever is round-1-confirmed → promote, then continue to
  the next candidate (stacking only non-conflicting wins); or (b) the backlog is exhausted with
  honest negatives → declare 88.55 the generalizable ceiling, stop accuracy spend, pivot to
  Time/Idea. Either way: end with a documented, honest conclusion, not an open loop.

---

## 7. Verification & state pointers

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests -v
python -m compileall -q src
python -m hackaithon_c.run --policy
.\neko-core.ps1 --list-workflows
.\neko-core.ps1 --input "<public-test.json>" --output-dir output-dryrun --dry-run
.\scripts\verify.ps1 -InputPath "<public-test.json>"
```

- State of the world: `notes/RESUME-HERE.md`, `notes/session-2026-06-12.md`, `notes/lessons.md`.
- Dead levers: §3 above + `notes/router-tir-measured-2026-06-13.md`.
- MTP (round-2 Time): `Dockerfile.gemma-mtp`, `docker/neko-entrypoint.sh`,
  `notes/mtp-measured-2026-06-13.md`, `scripts/gpu/run_mtp_server.sh`.
- Dev-only gate: `--allow-development-workflow` / `HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1` (keeps
  unmeasured strategies out of the contest path).
- Credentials (read from files, NEVER commit/echo): RunPod key + Docker Hub PAT paths in
  `notes/RESUME-HERE.md` §5. Public test (no labels): `Downloads/public-test_1780368312.json`.

---

## 8. One-paragraph goal prompt (paste to start a Codex work session)

> You are the Neko Core accuracy-research agent for HackAIthon 2026 Bảng C. Read
> `docs/CODEX-ACCURACY-RESEARCH-MISSION.md`, `AGENTS.md`, `notes/RESUME-HERE.md`, and
> `notes/lessons.md`. Your goal: raise *generalizable* accuracy on the 2000-question multilingual
> private test beyond the current `self_consistency` ≈ 88.55, **without any public-463-fitted or
> hard-coded logic** (apply the overfit test in §1 to every change). Work continuously through
> the ranked research agenda (§4) using the measurement loop (§5): research → config-gated
> implementation with a verification story → held-out per-bucket GPU A/B → round-1 confirmation —
> promoting a lever only when it is GPU-measured, generalizing, and round-1-confirmed. Treat
> measured negatives as wins and document every outcome in `notes/`. Keep the default contest
> path `self_consistency` until something is proven. Pause for owner sign-off only at GPU spend
> and leaderboard submission. If the backlog is exhausted with honest negatives, declare 88.55
> the ceiling and pivot to the round-2 Time/Idea story. Think deeply; do not patch-fix.
