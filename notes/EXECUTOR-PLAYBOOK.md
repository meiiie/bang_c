# EXECUTOR PLAYBOOK — Neko Core → top of the Bảng C leaderboard

Status: Active operating manual for the implementing agent (Fable 5)
Date: 2026-06-10
Read first, in full: `notes/README.md`, `notes/2026-06-10-baseline-85.53-diagnosis.md`,
`notes/2026-06-10-architecture-proposal.md`, repo `AGENTS.md`, repo `README.md`.

This playbook turns the architecture proposal into a **self-running loop**. You pick the
next smallest task, implement it surgically, **prove it works**, record it, and continue —
phase by phase — until the Definition of Done (§7).

---

## 1. Mission & target

Maximize **accuracy on the 2000-question multilingual private test** (80 pts), keep
inference time reasonable (10 pts), and tell a strong optimization story (10 pts).
North-star: **98–100 on the leaderboard.**

> Honesty (karpathy: don't hide confusion). 98–100 is a *stretch*. From 85.53 the
> **recoverable** errors are large and identified — silent over-confident wrongs,
> calc mis-routing, suppressed reasoning, overfit adjudicators, CJK blindness. Closing
> those is the job. The residual gap to 100 is bounded by raw model capability and by
> genuinely hard items. Chase the recoverable errors relentlessly; report the real
> number; never fabricate progress or hard-code answers to inflate a score.

## 2. Non-negotiables (rules & skills — obey on every change)

- **karpathy-guidelines** (the skill): (1) think before coding, surface assumptions &
  tradeoffs, ask when unclear; (2) simplest thing that works, nothing speculative;
  (3) surgical changes — touch only what the task needs, match existing style; (4)
  goal-driven — define a verifiable success criterion and loop until it passes.
- **AGENTS.md**: config-first; no god files; small modules with clear contracts; **never
  hard-code public/private answers, qids, or leaderboard observations**; keep data-
  dependent values in config; every change ships a **verification story**.
- **Contract**: read `/data/*_test.(csv|json)` → write `/output/pred.csv` with exactly
  `qid,answer`; **per-row letters from each row's own choices** (never assume A–D).
- **Runtime/Dev boundary**: the final container is offline & self-contained — no web, no
  subagents, no DB, no API keys. Dev-only tools must stay quarantined (`--policy` passes).
- **Anti-overfit (the whole point)**: nothing may be tuned to the 463 public items or to
  Vietnamese specifically. **Keep diacritics.** If a heuristic only helps one language or
  one known question, it's a liability — remove it or make it general & config-driven.
- **Models**: Gemma-4 (contest: Gemma 4 26B A4B QAT Q4_0 GGUF, local) + Qwen3.5 ≤9B;
  embed/rerank BGE-m3 / Qwen-Rerank. No other model families.

## 3. The autonomous loop protocol

Repeat until §7 is met:

1. **SELECT** the smallest next task that advances the current phase (§4).
2. **PLAN (write it down)**: state your assumption, the change, and the *verifiable
   success criterion* before coding. If genuinely ambiguous or risky, **pause & ask**
   (§5) instead of guessing.
3. **IMPLEMENT** surgically. New behavior → new small module + config key, not edits
   smeared across layers. Match existing style.
4. **VERIFY (must pass before continuing)** — the verification story:
   - `python -m unittest discover -s tests -v` → green (add/adjust tests for your change).
   - `python -m compileall -q src` → clean.
   - `.\neko.ps1 --doctor` and `.\neko.ps1 --policy` → ok / `verdict: pass`.
   - Dry-run contract on the public file → `pred.csv` valid (`--check-submission`).
   - A real sample run (model on) on a small `--limit`/`--run-dir`, then
     `--review-trace` and `--compare-traces` vs the previous run for **answer stability**.
   - **Local gold suite** (§6) → no regressions.
5. **RECORD**: append a dated `notes/` entry (what changed, evidence/numbers, decision)
   and a one-liner to `notes/lessons.md` if durable. Update `CHANGELOG.md` per
   `docs/release-process.md` when a phase lands.
6. **DECIDE**: criterion met → mark task done; phase exit criteria met → advance phase.
   Otherwise iterate. If a change doesn't help or regresses, **revert it** (keep only
   changes that improve reproducibility/robustness/accuracy — README "Development Loop").

Bias to **one change at a time** so each effect is measurable (README development loop).

## 4. Phases (chosen order: P0→P1→P2→P3→P4)

Every valid point from the teammate review is folded in: multi-label routing & diacritic
fix (P2), real calibration (P1), independent verifier & tie handling (P3), modular split
(P4). Order differs deliberately: build the reasoning/calibration capability **first** so
removing the overfit crutches (P2) doesn't cost accuracy.

### P0 — Safety net (enables honest measurement) — small
- Build a **local gold suite** (§6): the 5 known mini-eval labels + ~15–25 hand-authored
  items you can verify, spanning **VI/EN/KO/ZH + a few math/negation/reading** types, as
  a JSON fixture under `tests/` (this is a *test fixture*, not a contest answer key — it
  is your own authored regression set, fully allowed).
- Add a unit/dry-run check that the pipeline **routes and runs without crashing on
  non-VI/CJK input** (catches the `[a-z0-9]`/diacritic no-op class).
- **Exit when**: gold suite + smoke run green; baseline numbers recorded in notes.

### P1 — Reasoning + real confidence (biggest accuracy lever)
- New `strategies/self_consistency.py` + `calibration.py`. Enable **chain-of-thought**:
  generic, **language-neutral** system prompt (answer in the question's own language),
  higher `max_tokens`, then extract the letter via `normalize_answer` (`ANSWER: X`).
- **Self-consistency**: sample k reasoned answers (config `k`), majority vote;
  **confidence = agreement fraction** (replace all hard-coded confidences).
- Trace must capture the reasoning (dev only); `pred.csv` stays letter-only.
- **Exit when**: confidence is agreement-derived (no hard-coded constants in the live
  path), gold suite ≥ baseline, answer stability acceptable, token/sec cost measured and
  recorded (feeds P3 tiering). Risk-review now flags genuinely uncertain items.

### P2 — Remove overfit / go language-agnostic (de-risk transfer)
- Delete the bespoke `calculation.py` solvers, `principles.py` rules, and magic-constant
  `evidence.py` boosts (see audit §4). Replace with the P1 reasoning path (model computes;
  optional *generic* numeric self-check that never hard-codes a formula/answer).
- **Keep diacritics**; make routing **multi-label & language-neutral** (structural signals:
  #choices, digit/math-symbol presence, context-block length, script) — stop the if/elif
  collapse; drop diacritic-strip-for-routing. Make length thresholds script-aware.
- ⚠️ **PAUSE & ask before deleting** (public score may dip; see §5). Quantify the public-
  sample delta first; proceed only with sign-off.
- **Exit when**: no public-item-specific or VI-only logic remains in the live path;
  multilingual smoke improved; public-sample delta understood & accepted.

### P3 — Independent challenger + budget-aware tiering
- Add a **cross-model challenger**: Qwen3.5-8B judges/re-derives **only** low-agreement
  items (different model breaks self-confirmation bias). Fix tie handling (no A-biased
  default; real adjudication).
- **Tier compute**: high-agreement → 1 cheap pass; uncertain tail → escalate. Keep within
  a measured time budget (10 pts). All thresholds (`k`, agreement τ, escalation) in config.
- **Exit when**: escalation only fires on the uncertain tail; measured wall-time acceptable;
  accuracy/stability improved on gold + sample.

### P4 — Full modular split (Claude Code layering)
- Decompose `solver.py` (808) & `run.py` (648) into `routing/`, `strategies/`,
  `adjudicate/` (generic verifier only), `calibration.py`, `risk.py` — each a small typed
  contract, config-selected. **Behavior-preserving**: tests green and answers identical
  before/after (`--compare-traces` shows no answer changes).
- **Exit when**: no function > ~150 lines in the solve path; tests green; zero answer drift.

## 5. Guardrails & pause-and-ask triggers

**Always**: keep `pred.csv` contract valid; keep diacritics; keep `--policy` passing;
keep the runtime container offline/self-contained; one change at a time; revert changes
that don't help.

**Never**: hard-code answers/qids/formulas tied to specific items; add a VI-only or
single-language heuristic to the live path; ship dev-only artifacts into the container;
skip the verification story; chase the public number at the cost of generalization.

**PAUSE and ask the human (do NOT do autonomously)**:
- Any **leaderboard submission** (limited & outward-facing — the human decides when).
- **Deleting the overfit adjudicators** in P2 (confirm the public-sample dip is acceptable).
- Anything **irreversible or outward** (force-push, publishing a Docker image, deleting
  run artifacts you didn't create, spending on RunPod/GPU).
- A phase exit criterion you can't meet, or evidence that contradicts this plan — stop,
  report what's confusing, and ask (karpathy §1).

Everything else (implement → test → verify → record → iterate) proceeds **autonomously**.

## 6. Measuring progress without a full gold set

You do **not** have private/public answer keys. Use a layered signal stack:

1. **Local gold suite (your regression truth)**: the 5 mini-eval labels
   (`test_0002=B, test_0006=A, test_0007=B, test_0008=B, test_0009=C`) + your own
   hand-authored multilingual/typed items (P0). Must never regress.
2. **Self-consistency agreement** (post-P1): primary internal signal. Rising agreement on
   stable answers ≈ more reliable; low agreement marks the uncertain tail to escalate.
   (Caveat: agreement ≠ correctness — a model can be consistently wrong; pair with #1/#4.)
3. **Answer stability** (`--compare-traces`): detect regressions/drift between runs.
4. **Trace review / risk** (meaningful post-P1): fewer high-confidence-wrong patterns;
   shrinking fallback/blocked counts.
5. **Contract validity** every run (`--check-submission`).
6. **Leaderboard** = ground truth, but **limited & human-gated** (§5). Submit only at major
   milestones (end of P1, after P2, after P3) and record the number in notes.

Prefer iterating on the **actual contest model (local Gemma 4 26B Q4)** when feasible —
results from the NVIDIA 31B dev path may not fully transfer (26B QAT Q4 ≠ 31B).

## 7. Definition of Done (overall)

- All phases P0–P4 exited per their criteria.
- Live path contains **no overfit/VI-only/public-item-specific logic**; diacritics kept;
  routing & prompts language-neutral; confidence is calibrated; verifier is independent.
- `unittest` green, `compileall` clean, `--doctor`/`--policy` pass, `pred.csv` contract
  valid, gold suite green, no answer drift from the last accepted run.
- Final self-contained **Gemma local Docker image** rebuilt, smoke-validated, and the
  full public run reproduced from the image (per `docs/submission-readiness.md`).
- Leaderboard number recorded; method write-up (idea 10 pts) drafted from `notes/`.
- Every phase documented in `notes/` with evidence; `CHANGELOG.md` updated.

## 8. Command quick-reference (Windows PowerShell)

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests -v          # tests green
python -m compileall -q src                       # compiles
.\neko.ps1 --doctor                               # env/contract health
.\neko.ps1 --policy                               # runtime/dev boundary: verdict pass
.\neko.ps1 --list-workflows
# dry-run contract (no model):
.\neko.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output-dryrun --trace-dir traces-dryrun --dry-run
.\neko.ps1 --check-submission "output-dryrun\pred.csv"
# real sample run (model on) + review + compare for stability:
.\neko.ps1 --workflow contest-strict --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --run-dir run-iter --limit 30
.\neko.ps1 --review-trace run-iter\traces
.\neko.ps1 --compare-traces run-prev\traces run-iter\traces
.\scripts\evaluate.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" -Limit 20
```
Dev model: set `HACKC_PROVIDER`/`--profile nvidia-gemma31b-api` (+ `NVIDIA_API_KEY`) or
local `HACKC_PROVIDER=local_llamacpp` with the Gemma GGUF. Public file = 463 questions.
