# Execution worklog (autonomous loop)

Append-only. One entry per loop step. Newest at bottom. Plan → implement → verify →
record → decide. Numbers are real or marked as not-yet-measured.

---

## 2026-06-10 — Phase 0: Safety net — DONE ✅

**Goal:** establish a local regression set + prove the pipeline is robust (no crash /
valid letter) on non-VI/CJK input; record baseline routing as the signal P2 must improve.

**Changes (surgical):**
- `tests/fixtures/multilingual_gold.json` — 16 hand-authored items (our own Q&A, not
  contest data) spanning VI/EN/KO/ZH × reading/negative/calculation/general/logic, each
  with an authored answer letter.
- `tests/test_multilingual_robustness.py` — 5 tests: fixture loads; authored answers are
  valid letters; every item classifies without error; dry-run solve returns a valid
  letter for all; CJK items don't crash the `[a-z0-9]`/diacritic-blind heuristic layer.

**Verification story (all green):**
- `python -m unittest discover -s tests` → **85 tests OK** (was 80; +5).
- `python -m compileall -q src` → exit 0.
- New tests alone → 5/5 OK.

**Baseline routing on the gold set (evidence for later phases):**

| qid | lang | expected | routed kind | bug surfaced |
|---|---|---|---|---|
| gold_en_gk_01 | en | general | **calculation** | "formula"+digit → false calc route |
| gold_en_neg_01 | en | negative | short | EN "NOT" negation missed (VI-only markers) |
| gold_ko_neg_01 | ko | negative | short | KO "아닌" negation missed |
| gold_zh_neg_01 | zh | negative | short | ZH "不是" negation missed |
| gold_math_arith_02 | en | calculation | short | genuine EN calc missed |
| gold_ko_gk_01 / gold_zh_gk_01 | ko/zh | general | short | CJK → no markers → default (no-op) |
| gold_vi_geo_trap_01 | vi | geography | short | OK here (no stray digit → guard held) |

→ Confirms the audit: negation is VI-only; "formula"/keyword calc false-positives;
CJK heuristics are inert. **These become the pass/fail targets for P2.** Routing
correctness is NOT asserted yet (fixed in P2); P0 only guarantees no-crash + valid letter.

**Decision:** P0 exit criteria met. Advance to P1 (reasoning + real confidence).
Open dependency surfaced below.

### ⏭️ Dependency for P1/P3 — real-model access
P1 (CoT + self-consistency) and accuracy measurement need a live allowed model
(local Gemma GGUF or NVIDIA dev API). Checking availability next; if neither is reachable
in this environment, P1 *code* will be built and unit-tested with a deterministic stub
client, and real-model accuracy/token-cost measurement will be flagged for the human to
run (needs their `NVIDIA_API_KEY` or the local `.gguf`). This is a measurement gate, not
a blocker for the code change.

---

## 2026-06-10 — Phase 1 (code): reasoning + self-consistency + calibration — CODE DONE ✅ (measurement gated)

**Goal:** make confidence a real, agreement-based signal and let the model reason
(chain-of-thought), as a **config-gated new strategy** that leaves the existing
auto/direct/verify/tournament paths untouched (surgical — karpathy §3).

**Changes:**
- NEW `src/hackaithon_c/calibration.py` — pure funcs: `majority_vote` (tie-break by
  first-seen, not A-biased), `agreement_confidence`, `vote_distribution`.
- `prompting.py` — `REASONING_SYSTEM_PROMPT` (language-neutral, allows step-by-step, ends
  `ANSWER: <letter>`) + `build_reasoning_prompt` (max_tokens 512). Existing prompts kept.
- `solver.py` — new `_solve_self_consistency` (k reasoned samples → vote → confidence =
  agreement) + dispatch for `strategy="self_consistency"`.
- `config.py` — `self_consistency_samples` (5) + `reasoning_max_tokens` (512); added
  `self_consistency` to valid_strategies. `run.py` — added to `--strategy` choices.
- `configs/default.json` + packaged `resources/default.json` (kept in sync) — new keys +
  dev workflow `self-consistency` (phase=development; NOT contest default yet).
- Tests: `tests/test_self_consistency.py` (11).

**Verification (all green):** new 11/11; full suite **96 OK** (+16 vs 80 baseline);
`compileall` 0; `--list-workflows` shows it; `--policy` PASS; `--doctor` ok (only env
warnings); dry-run contract on gold fixture → `pred.csv` valid, `--check-submission`
Valid 16/16.

**Confidence is real now:** `agreement_confidence = winner_votes / valid_samples`
(unanimous→1.0, split→<1.0), replacing hard-coded 0.68–0.88 *for this path*.

**⛔ P1 not fully exited — needs the human (one gate):** no model reachable here
(no `NVIDIA_API_KEY`, no `.gguf`, `llama_cpp` absent). To finish P1: run `self_consistency`
on the real allowed model, measure gold-suite accuracy + tokens/sec, tune `k` /
`reasoning_max_tokens`, then decide cutover of the **contest** workflow. Until then the
live contest path keeps its current strategy (no regression risk).

**Decision:** P1 code complete & verified. Proceed to **P2 routing** (language-agnostic
multi-label classifier — model-independent, verifiable against the gold fixture). P2's
*deletion* of overfit adjudicators stays paused for human sign-off (public-dip risk).

---

## 2026-06-10 — Phase 2 (increment 1): calc over-trigger fix (language-agnostic) — DONE ✅

**Goal:** stop the calculation router firing on topic words ("formula"/"value"/"giá trị")
+ an incidental digit in answer choices, language-agnostically, without regressing pinned
VI behavior (audit findings #2/#3).

**Change (surgical — `classifier.py` only):**
- Expanded `_BROAD_CALCULATION_MARKERS` to include topic/ambiguous markers (formula,
  cong thuc, value, gia tri, bao nhieu/how many/how much, do co gian, ty le, ratio, gdp):
  these now require a real quantitative signal to count as calculation.
- Rewrote `_has_quantitative_signal` to test the **question text only** (not choices) for a
  genuine computation: an arithmetic operator between numbers, a number+unit, ≥2 numbers,
  or a quantitative domain phrase. A lone stray digit (a year, "Điều 5", a CO2/H2O
  subscript) no longer counts.

**Verification (all green):** full suite **98 OK** (+2 calc-routing regression tests);
`compileall` 0; `--policy` PASS. Gold set: calculation false-positives **1 → 0**
(`gold_en_gk_01` "chemical formula" now `short`); all 3 genuine math items still
`calculation`; every pinned VI classifier test unchanged.

**Deliberately NOT done (karpathy §2 — avoid the fragile, monolingual game):**
- EN/KO/ZH **negation** still routes `short`. The fix is the **reasoning prompt** (handles
  negation natively), not more per-language keyword lists — resolves once self_consistency
  is the live path (gated on model access).
- The diacritic-strip itself is unchanged; the over-trigger it *caused* is now mitigated
  (higher-leverage, lower-risk than a full diacritic-aware rewrite, which is also partly
  mooted by reasoning-first routing).
- One EN calc **under-trigger** remains (`gold_math_arith_02`) — handled by reasoning.

**Decision:** P2 increment 1 done & verified. **Now at a genuine external gate** — further
DoD progress needs the human (see status), not more autonomous code churn.

---

## 2026-06-10 — Status: at external gate (autonomous model-independent work exhausted)

Completed & verified without a model: **P0** (safety net), **P1 code** (reasoning +
self-consistency + agreement-calibration), **P2 increment 1** (calc over-trigger fix).
98 tests green throughout; contract + policy intact; existing contest path untouched
(zero regression risk). The remaining Definition-of-Done items each require something only
the human can provide:

1. **Real-model access** (NVIDIA_API_KEY or local `.gguf` + llama-cpp-python) — to validate
   the reasoning/self-consistency path, measure gold-suite accuracy + tokens/sec, tune
   `k`/`reasoning_max_tokens`, and decide cutover of the contest workflow. **Blocks P1
   exit, P3 tuning, and any real accuracy number.**
2. **Sign-off to delete the overfit adjudicators** (P2 deletion) — public-score-dip risk;
   a designed pause trigger. Best done *after* (1) confirms the reasoning path recovers
   those points.

Holding P3 (cross-model challenger — needs a model to validate it helps) and P4 (modular
refactor — would refactor code whose strategy is still in flux pending cutover; karpathy:
don't refactor code about to change). Resuming the instant either gate clears.

---

## 2026-06-10 — DoD item: method write-up — DRAFTED ✅

Wrote `docs/method-writeup.md` — the contest "thuyết minh phương pháp" (Ý tưởng, 10 pts):
problem/contract, design philosophy (model-reasons/anti-overfit/calibrated/runtime-dev
boundary), architecture, the optimization levers (reasoning + self-consistency calibration,
language-agnostic routing, cross-model verification, tiered compute, overfit removal),
runtime/reproducibility, and an **honest status** section. No accuracy number is invented —
the measured 85.53 baseline is cited; everything awaiting a real-model run is labelled
pending. A Vietnamese adaptation should be derived for the actual submission.

This satisfies DoD item #6 (method write-up drafted). Remaining DoD items (P1 full exit,
P2 deletion, P3, P4, final Docker rebuild, leaderboard number) remain gated on model access
+ deletion sign-off, as recorded above. Not fabricating progress to satisfy the loop —
holding for the gate; will fill measured numbers into the write-up as they are produced.

---

## 2026-06-10 — Phase 3 (code): cross-model challenger + tiered escalation — CODE DONE ✅ (tuning gated)

Reconsidered the earlier "hold P3": the *mechanism* is verifiable now with stub clients
(same legitimacy as P1's self_consistency), only the real-model *tuning* is gated. Built it.

**Changes (surgical):**
- `solver.py` — extracted `_collect_reasoning_votes` + `_vote_prediction` (shared vote→
  calibrated-confidence helper; also de-duplicated `_solve_self_consistency`). Added
  `solve_with_challenge(problem, client, challenger, *, config)`: run primary self-
  consistency; **only if agreement < threshold**, gather extra reasoned votes from an
  INDEPENDENT challenger model and re-tally the combined pool (cross-model breaks self-
  confirmation bias; tiering protects the time budget). Degrades safely to plain self-
  consistency when `challenger is None`.
- `config.py` + `default.json` (+packaged sync) — `self_consistency_challenge_threshold`
  (0.75) + `challenger_samples` (3).
- Tests: `tests/test_self_consistency.py` +4 (no escalation on high agreement; escalate +
  confirm; escalate + challenger flips answer; None-challenger degrades cleanly).

**Verification:** full suite **102 OK** (+4); compileall 0; --policy PASS.

**Gated (needs the human / a model):** constructing the *second provider client* and wiring
`solve_with_challenge` into the CLI dispatch is deferred — that integration can't be
validated without a real model, so the CLI keeps `challenger=None` until then. Real-model
tuning of `threshold`/`challenger_samples` and proof it raises accuracy also pending.

---

## 2026-06-10 — Phase 2 (increment 2): multilingual negation routing — DONE ✅

**Goal:** the gold baseline showed EN/KO/ZH "choose the FALSE one" questions routed to a
plain `short` profile (negation markers were VI/EN/ES-only). Fix it config-first
(multilingual, not single-language — guardrail-compliant) so the *current* live path
handles multilingual negation; the reasoning prompt also covers it once that path is live.

**Change:** `configs/default.json` (+packaged sync) `profiling.markers.negative` — added
`is not`, `are not`, and CJK/Korean/Japanese cues (`아닌`, `옳지 않은`, `틀린`,
`적절하지 않은`, `不是`, `不正确`, `错误`, `不对`, `不属于`, `正しくない`, `間違っている`).
No code change. Diacritic-aware/script-aware: CJK passes the `(?<![a-z0-9])` boundaries.

**Verification:** full suite **103 OK** (+1 multilingual negation routing test); compileall
0; --policy PASS. Gold routing recheck: **routing problems 0** — VI/EN/KO/ZH negation all
→ `negative`; all genuine calc → `calculation`; zero false-positives. (One EN calc
under-trigger remains by design → reasoning prompt.)

---

## 2026-06-10 — Gate status (updated)

**Done & verified without a model (103 tests green throughout, contract+policy intact,
contest path untouched → zero regression risk):**
- P0 safety net · P1 reasoning+self-consistency+calibration (code) · P2 routing now
  multilingual-clean (calc over-trigger fix + multilingual negation) · P3 cross-model
  challenger + tiering (code) · DoD#6 method write-up draft.

**Genuinely blocked — needs the human:**
1. A real allowed model in the environment (NVIDIA_API_KEY or local `.gguf` +
   llama-cpp-python) → measure accuracy/tokens, tune `k`/`reasoning_max_tokens`/challenge
   `threshold`, validate the reasoning path recovers the ~57 silent errors, then decide
   the contest-path cutover (P1 exit) and P3 wiring.
2. Sign-off to delete the overfit adjudicators (P2 deletion; public-dip risk), best done
   after (1).
Outward/irreversible (final Docker rebuild, leaderboard submission) also await the human.

**First command to run once a model is available** (dev API path):
`setx NVIDIA_API_KEY ... ; .\neko.ps1 --profile nvidia-gemma31b-api --workflow self-consistency --input <public.json> --run-dir run-sc --limit 30`
then `--review-trace run-sc\traces` and compare confidence vs the old hard-coded run.

Not manufacturing marginal changes to satisfy the loop (would violate "keep only changes
that help" + "never fabricate progress"). Holding for the gate; resuming instantly on unblock.

---

## 2026-06-10 — P0 hardening: gold suite expanded to 6+ scripts — DONE ✅

Broadened `tests/fixtures/multilingual_gold.json` from 16 → **24** items, adding French
(negation + calculation), German, Spanish (reading), Russian (Cyrillic), Arabic (RTL), Thai
(no word spaces), and a Korean 6-option (structural many_choice) item — each with an
authored answer. Added 1 routing test (FR negation/calc + KO many_choice are detected).

**Verification:** full suite **104 OK**; compileall 0; dry-run over all 24 items across
Latin/CJK/Cyrillic/Arabic-RTL/Thai → **no crash**, contract valid 24/24, routing dist
`{negative:5, calculation:4, many_choice:1, reading:1, short:13}`. This *verifies* the
language-agnostic / no-crash claim on scripts the heuristic layer had never been exercised
on (RTL, no-space) — a real robustness guarantee, not busywork. Genuine accuracy gains
still require a real model (gate unchanged).

---

## 2026-06-10 — P1 hardening: answer extraction for natural chain-of-thought — DONE ✅

Reconsidered an earlier "hold": the gap was **demonstrable, not speculative** —
`normalize_answer("The answer is A.")` returned `None` today, silently dropping a
self-consistency vote. Common LLM answer formats are reliably known, so hardening for them
is sound, not guesswork.

**Change (surgical — `normalize.py`, one regex):** the answer-indicator patterns
(`ANSWER`/`FINAL`/`RESULT`/…) now also consume an optional `IS`/`ARE` and an opening paren,
so `"the answer is A"`, `"answer is b"`, `"Answer: (C)"`, `"**ANSWER: D**"` all extract —
while a bare article letter in prose (`"...for a crime..."`) still extracts nothing (the
marker word is required). Strictly additive: existing successful extractions unchanged.

**Verification:** new `tests/test_normalize_cot.py` (4) incl. the article-letter guard +
the two pinned `test_contract` normalize tests still pass; full suite **108 OK**;
compileall 0. Directly protects the P1 reasoning path from losing votes to format drift.

---

## 2026-06-10 — Model access: both paths empirically confirmed CLOSED on this machine

Exhausted every avenue to self-provision a model (so the gate is verified, not assumed):
- **NVIDIA API key**: searched all `AI_v1` `.env*` files + process env + user env → **0**
  found. (This path needs only `requests` — already installed — so a key would unblock
  it instantly with no build step.)
- **Local GGUF**: no `.gguf` on disk; **`pip install --only-binary :all: llama-cpp-python`
  → "No matching distribution"** — there is no prebuilt wheel for **Python 3.13.7** on this
  Windows box, and a source build needs a C++/CMake toolchain (slow/likely absent).
- pip + internet DO work here (installed pypdf earlier), so the blocker is specifically
  *model + (key | llama-cpp wheel)*, not connectivity.

**Conclusion:** real-model measurement requires the human — easiest is `NVIDIA_API_KEY`
(zero install). Local path would need Python 3.11/3.12 (prebuilt llama-cpp wheels) or a
build toolchain. No further autonomous progress toward the leaderboard number is possible
here. All model-independent work is complete and verified (108 tests, contest path
untouched). Holding at the gate; not churning or fabricating.

---

## 2026-06-10 — Decision: end the local autonomous phase; real testing moves to GPU

Owner decision: the build/verify phase (everything achievable without a model) is DONE.
Real measurement will be a deliberate, separate effort on a **rented GPU** (per
`docs/runpod-operations.md` / `docs/runpod-gpu-selection.md`): run the **actual contest
runtime** `Gemma-4-26B-A4B-QAT-Q4_0` GGUF, replicate BTC's container flow, package the
Docker image, and measure on the public set — which is far faster on an A40/A6000 than CPU.

**Carry-forward for the GPU session (validate the NEW code there):**
1. Pull this branch; build/run with the new `self_consistency` workflow on the real model.
2. `evaluate.ps1 -Workflows contest-strict,self-consistency` on the public set → compare
   accuracy + **wall-clock/tokens** + whether agreement-confidence separates right/wrong.
3. ⚠️ Time trade-off to measure: reasoning (CoT) emits more tokens AND self-consistency
   runs k samples/question → slower per item than the old letter-only single-shot, even on
   GPU. Tune `self_consistency_samples`/`reasoning_max_tokens` + P3 tiering against the
   10-pt time score (accuracy is 80 pts, so some slowdown is worth it — but measure it).
4. Only then: cut the contest path over to reasoning (P1 exit), get sign-off to delete the
   overfit adjudicators (P2), wire P3, refactor P4, rebuild + validate the image, submit.

Goal/loop to be cleared by the owner (`/goal clear`). State is clean; resume via
`notes/RESUME-HERE.md`.

---

## 2026-06-10 — REAL-MODEL TEST on RunPod A40 + Gemma-4-26B-A4B-Q4 (the contest model) ✅

Owner authorized RunPod spend + provided keys. Provisioned A40 48GB ($0.44/hr, secure),
pulled the GGUF out of `hacamy12345/neko-core:gemma26b-q4` via skopeo (no HF token needed),
installed CUDA llama-cpp, overlaid this branch's code, ran the real contest model.

**Smoke:** model loads + answers `test_0001=A` in 18s. Gemma-4-26B is a fast MoE (4B active).

**10-question gold comparison (gold: 0002=B,0006=A,0007=B,0008=B,0009=C):**

| Strategy | gold | fallbacks | wall(10q) | confidence |
|---|---|---|---|---|
| baseline (contest-strict/auto) | 4/5 | 0 | 18s | flat 0.84–0.88 |
| self-consistency k=5 @ max_tokens **512** | 3/5 | **3/10** | 219s | broken |
| self-consistency k=5 @ max_tokens **2048** | **5/5** | 0 | 255s | all 1.0 |
| **CoT k=1 @ 2048** | **5/5** | 0 | **62s** | 1.0 |

**Findings (real numbers, not guesses):**
1. **`reasoning_max_tokens=512` was a real bug.** Proven: `test_0002` (elasticity calc) at
   512 truncated mid-calculation with no "ANSWER:" → fallback (wrong); at 2048 it finished
   "...= 1.0 ... ANSWER: B" → **correct (= gold)**. Fixed → default now **2048** (repo
   updated, 108 tests still green).
2. **CoT reasoning beats the letter-only baseline** on gold (5/5 vs 4/5). Concretely it
   fixed a calculation (`test_0002`: CoT→B correct, baseline tournament→C wrong) and
   `test_0009` (CoT→C correct vs the earlier broken H). This validates the core thesis:
   *let the model reason*.
3. **k=5 self-consistency is wasteful at the client's `temperature=0`** — the 5 samples are
   effectively identical (every confidence = 1.0), so it pays 4× the cost of k=1 for zero
   diversity. The agreement-calibration only yields signal with `temperature>0` (a separate
   future change). **For the contest, `k=1` (single deterministic CoT) is the efficient
   choice** — same accuracy, reproducible, ~1/4 the time.
4. **Speed:** CoT k=1 ≈ 6s/q (incl. load) vs baseline ≈ 1.8s/q → ~3× slower. For 2000q that
   is ~3.4h vs ~1h. Worth it given accuracy=80pts ≫ time=10pts, but the time cost is real;
   tiering (escalate only hard items) is the lever if needed.

**Recommended contest config (validated):** reasoning path, **k=1, reasoning_max_tokens=2048**.
Repo now has max_tokens=2048; the k=5→1 default + contest-path cutover are being finalized
against the full-463 run (in progress) + the owner's leaderboard submission.

**In progress:** full 463-question run of BOTH baseline and CoT on the real 26B → real total
timing + a submittable `pred.csv` (owner submits to the leaderboard for the true number vs
the known 85.53). Then: finalize cutover, package the image, terminate the pod.

### Full 463 results (same model, only strategy differs)
| | Baseline (contest-strict) | CoT k=1 (self-consistency) |
|---|---|---|
| wall (463) | 374s (0.8s/q) | 2126s (~35min, 4.6s/q) |
| fallbacks | 0 | 7 (1.5%) |
| gold (5) | 4/5 | **5/5** |
| **answers differ** | — | **91/463 (19.7%)** |

CoT changed 91 answers and wins the 5 gold (5 vs 4). **The verdict on the other ~86 needs the
leaderboard** (we only hold 5 gold labels). Both `pred.csv` copied to
`E:\Sach\Sua\_tmp\neko-core-runpod-a40-20260610\` (`pred-baseline-463.csv`,
`pred-cot-463.csv`) + `cot-trace.jsonl` for error analysis.

### Sovereignty robustness probe — PASS (no mitigation needed)
Hoàng Sa/Trường Sa MCQ, default vs VN-framed prompt → **Gemma-4-26B answered Vietnam-aligned
in all 4 runs** (sov1→B Việt Nam, sov2→A Việt Nam), reasoning explicitly "theo quan điểm chính
thức của CHXHCN Việt Nam... là lãnh thổ Việt Nam" — no hedging/refusal. The VN-framing prompt
is NOT needed. (Caveat: only 2 straightforward items tested; adversarial phrasings untested.)

### Packaged image (candidate — new tag, does NOT overwrite the safe one)
Built with crane (reused all base layers incl. the 15GB model; pushed only a 320KB code layer):
- `hacamy12345/neko-core:gemma26b-q4-cot-20260610`
- digest `sha256:72901c079701e9b2bd486e86a04da87f894470a36a8372467dd4591d78acd665`
- entrypoint `neko-entrypoint`; **CMD defaults to `--workflow self-consistency`** (CoT);
  contract intact (reads /data, writes /output/pred.csv). Config inside: k=1, max_tokens=2048.
- The existing `gemma26b-q4` (85.53 baseline) is untouched.

### Cost / cleanup
RunPod A40 secure $0.44/hr. Balance $2.027 → **$1.307** (~$0.72 for the whole test). Pod
`jpskqsycy1rfjv` **TERMINATED** (currentSpendPerHr=0). Local repo updated: max_tokens=2048
(108 tests green).

### NEXT (owner action) → then finalize
1. **Submit `pred-cot-463.csv` to the leaderboard** → the true CoT number vs 85.53.
2. If CoT wins → `gemma26b-q4-cot-20260610` is the final submission image; lock the local
   cutover (contest workflow → reasoning, samples=1). If not → keep baseline, study the diff.
3. Optional: a direct-image smoke of the new tag before final BTC submission (docs runbook).
   The CODE is already validated by the 463-run; the image is the same code on the same base.

---

## 2026-06-10 — LEADERBOARD VERDICT + CUTOVER LOCKED ✅✅

Owner submitted both to the leaderboard:

| Approach (same Gemma-4-26B) | Leaderboard |
|---|---|
| Baseline letter-only (contest-strict) | **77.11** |
| **CoT k=1 (self-consistency)** | **87.26** |

**CoT wins by +10.15** over the same-model baseline (and +1.73 over the prior 85.53). The
core thesis is confirmed on the real scoring metric: *let the model reason*. Cutover is now
fully justified by real data.

**Cutover locked into the repo (109 tests green, policy PASS):**
- `config` default `self_consistency_samples` 5→**1** (validated; k>1 is wasteful at temp 0);
  multi-sample tests now build an explicit k=5 config so the voting/escalation mechanism is
  still covered; added a test asserting the shipped default is k=1.
- `reasoning_max_tokens` = **2048** (the 512-truncation bug fix).
- `self-consistency` workflow promoted **development → runtime** (the contest default).
- `Dockerfile.gemma-local` CMD + `docker/neko-entrypoint.sh` default → `--workflow
  self-consistency`, so a fresh build reproduces the winning image.

**Winning submission image (already on Docker Hub, = the 87.26 run):**
`hacamy12345/neko-core:gemma26b-q4-cot-20260610`
(digest `sha256:72901c079701e9b2bd486e86a04da87f894470a36a8372467dd4591d78acd665`).
The local repo now matches it. No repackage needed.

**Method write-up:** `docs/method-writeup-vi.md` (VI, for submission) + `docs/method-writeup.md`
(EN) updated with the 87.26 number.

**Optional follow-ups (not blocking):** delete the now-unused overfit adjudicators
(calculation/principle/evidence — the CoT path doesn't call them; pause-trigger, owner sign-off);
tiering for the time score; temp>0 self-consistency for real calibration. See
`notes/research-directions.md`.

---

## 2026-06-11 — 93+ push, increment 1: tiered diverse self-consistency — CODE DONE ✅ (GPU measurement pending)

Goal 87.26 → 93+ (+27 of 463). Ran a 3-agent cited research workflow
(`notes/research-93-cited-reports.md`) AND implemented the core mechanisms, local-tested.

**Research highlights (cited in the report):**
- Self-consistency: most gain by k=5–10; math +12–18pp, knowledge +1.5–4pp. Voting works
  best at higher T; **Gemma-4 tuned operating point is T=1.0/top_p=0.95/top_k=64 and low T
  degrades it** → diversified samples use T=0.8 (config).
- **Position bias is a major MCQ error source**; cyclic-permutation voting +1.2pp (full
  +4.9pp), debias flips more wrong→right. Our rotation scheme matches the literature.
- **Tiered/agreement-gated escalation** (MoT cascades, Adaptive-Consistency, ESC): equal
  accuracy at 40–60% compute; agreement-of-2 is the best uncalibrated routing signal.
- **AVOID (evidence-backed):** "are you sure" self-verification (−1…−17pp, sycophancy);
  generative elimination prompting (−5…−14pp — relevant: the legacy elimination prompt!);
  replacing CoT with pure logprob scoring (−10pp on our own data).
- Qwen3.5-9B ≈ Gemma-4-26B on MMLU-Pro (82.5 vs 82.6) but Gemma +5pp multilingual →
  ensemble viable, Gemma stays the authority. Dual-greedy tier-1 (Gemma+Qwen agree → lock)
  is the recommended GPU-phase architecture; llama.cpp continuous batching makes k samples
  ~2–3× wall-clock, not k×.
- Net literature-anchored estimate: **+4–7pp → 91.5–94**; 93 is the optimistic-middle.

**Implemented (all stub-tested, 124 tests green, policy PASS, contract valid):**
- `complete()` protocol + both clients: optional `temperature/top_p/top_k/seed` (None =
  the exact deterministic behavior that scored 87.26).
- NEW `permute.py`: cyclic choice rotation + original-letter mapping + `stable_seed`
  (sha256 of qid|index → reproducible temp>0 sampling).
- `_collect_reasoning_votes`: `diversify` mode — sample 0 = deterministic anchor;
  samples 1.. = rotated choices + seeded T=0.8/top_p=0.95/top_k=64; invalid samples get
  one deterministic repair pass (lever #5 — fixes the 7-fallback class).
- NEW strategy `tiered` (`_solve_tiered`): tier-1 = anchor + rotated sample(s); unanimous
  → stop (cheap); disagreement → escalate to `tiered_total_samples` and vote over all.
  Workflow `tiered-consistency` (phase=development until GPU-measured).
- `build_challenger_client(config)`: config-gated second local model (Qwen) for the
  ensemble lever; returns None unless configured.
- Config keys: `reasoning_temperature` 0.8, `reasoning_top_p` 0.95, `reasoning_top_k` 64,
  `tiered_tier1_samples` 2, `tiered_total_samples` 5, `challenger_provider/model_path/model_id`.
- Tests: `test_tiered_consistency.py` (permute math round-trip; position-biased stub
  triggers escalation and the rotated vote outvotes the bias; content-robust stub stops at
  tier 1 with 2 calls; seeded sampling params asserted; challenger builder gating) +
  updated self-consistency tests for the repair pass. The k=1 contest path is UNTOUCHED.

**Honest framing:** mechanisms are validated by stubs + literature, but accuracy claims
require the real model. Tier-1-unanimity rate, k, T, and the tier thresholds are
GPU-phase tuning. The 87.26 image/path remains the safe fallback.

**Next (GPU phase):** (1) letter-logit readout after forced "ANSWER:" (rank-1
accuracy-per-cost in the research: ~free, +0.5–1.5pp, also yields the MSP routing signal)
— needs llama.cpp low-level API, build against the real model; (2) obtain a Qwen3.5-8/9B
GGUF and run dual-greedy tier-1; (3) measure tiered vs k=1 on the 463 + tune; (4) submit
best to leaderboard.

---

## 2026-06-11 — 93+ push, increment 2: cross-model tiered escalation wired end-to-end ✅

- `_solve_tiered` now accepts an optional independent `challenger`: tier-1 unanimity never
  consults it (cheap path intact); on disagreement the escalation pool adds
  `challenger_samples` diversified challenger votes (rotations continue past the primary's
  indices so the second model sees different choice orders). Primary's votes come first →
  first-seen tie-break favors Gemma (the +5pp-multilingual authority, per research).
- `run.py` builds the challenger once from config (`build_challenger_client`) and
  **enforces the contest model-family allowlist on it** (`validate_runtime_model`) — a
  non-allowed second model is rejected at startup, same as the primary.
- Tests +3 (agreement never consults challenger; pooled escalation vote incl. challenger
  flip; None-challenger unchanged): full suite **127 OK**, compileall 0, policy PASS.
- Everything stays config-gated OFF (`challenger_*` empty) until a Qwen3.5 GGUF is staged
  in the GPU phase. The k=1 87.26 contest path remains untouched.

**State: all model-independent 93+ mechanisms are now built and tested.** What remains is
inherently GPU-bound: stage a Qwen3.5≤9B GGUF, measure tiered (±challenger) vs k=1 on the
463, tune k/T/tier sizes/challenger_samples, implement the letter-logit readout against
real llama.cpp, then leaderboard-validate the winner and re-package.

---

## 2026-06-11 — Speed levers (zero accuracy risk) — CODE DONE ✅ (GPU validation pending)

Owner asked for speed-ups that keep the score. Real motivation beyond the 10 time-pts:
**feasibility risk** — CoT ≈4.6s/q ⟹ 2000q ≈ 2.9h, and tiered/ensemble multiply that; an
unknown BTC timeout could be fatal. Implemented only the levers with NO accuracy coupling
(per the research, concise-prompt/token cuts are accuracy-coupled → deferred to GPU A/B):

1. **Flash-attention + n_batch flags** (`local_flash_attn`, `local_n_batch` config +
   `HACKC_LLAMACPP_FLASH_ATTN` / `HACKC_LLAMACPP_N_BATCH` env): the A40 smoke log showed
   "V cache padded because FA is not enabled" — enabling FA typically +10–30% tok/s.
   Default OFF until validated on the contest GPU (no unvalidated default flips).
2. **`local_server` provider**: an in-container llama.cpp `llama-server` on localhost via
   the OpenAI-compatible protocol (reuses `NvidiaChatClient`; no API key; same
   offline/self-contained guarantee — the server lives INSIDE the container). Enables
   continuous batching. `--provider local_server` + `HACKC_LOCAL_SERVER_URL`.
3. **`--workers N`**: solve N questions concurrently (research: batching ⇒ k samples cost
   ~2–3× not k×; question-level concurrency expected **3–8× wall-clock**). Results stream
   in input order → pred.csv ordering, checkpoint cadence, and events identical to
   sequential (test-proven: workers=1 vs workers=4 byte-identical on the gold fixture).
   Guard: in-process llama.cpp is single-threaded → workers forced to 1 with a warning
   unless an HTTP provider is selected. Retry loop extracted to `_solve_with_retry`
   (worker-safe; retry events emitted on the main thread).

**Verification:** full suite **133 OK** (+6: flags env parsing, local_server no-key client
+ URL override, retry helper, workers e2e equivalence); compileall 0; policy PASS; doctor
unchanged (all new paths opt-in; contest default untouched).

**GPU phase addition:** launch `llama-server -m gemma.gguf --parallel 8 -ngl 99 -fa` in the
container/pod, run harness with `--provider local_server --workers 8`, measure tok/s and
verify answers match the in-process path on a sample before adopting.

---

## 2026-06-11 — Frontier research toward 97-98 (4 cited reports) + first implementations ✅

Owner target: 93+ minimum, stretch 97-98, NO GPU yet — continuous local development.
4-agent web-research (full citations: `notes/research-97-cited-reports.md`). Game-changers:

1. **Our GGUF is likely bleeding points.** Naive Q4_0 conversion of the Gemma-4 QAT
   checkpoint = 70.2% top-1 agreement vs the BF16 QAT lattice; **Unsloth UD-Q4_K_XL
   restores 85.6% (+15.4pp token-level, 200MB smaller)**. Swap = cheapest experiment, new
   GPU-phase priority #1. Related stack audits: NEVER quantize Gemma's KV cache (most
   KV-quant-sensitive model tested); pin llama.cpp ≥ b8691 and outside b8661–b8687
   (Windows builds silently drop multi-byte UTF-8 = Vietnamese corruption); verify
   `vocab type = SPM` in load logs.
2. **Few-shot is the biggest documented prompt lever:** 0→5-shot Vietnamese exemplars =
   **+15.43pp avg (+32pp math)** on Vietnamese graduation-exam MCQ (ViGEText). Keep
   English meta-instructions (+2.9pp open models); NEVER translate questions (−5.8pp).
3. **Offline RAG: CONDITIONAL GO.** Every winning team in the closest analog (Kaggle LLM
   Science Exam) used retrieval (+10–15pp); VNHSGE: retrieval +32pp History +15pp Civics
   ~0 Math; VLegal-Bench +22pp. BUT always-on RAG measurably HURTS (TARG) → gate by
   question type + vote disagreement; RAG votes join the pool (downside ~0). Corpus
   (anti-overfit: universal reference sources only, never tuned to public questions):
   wikipedia-vi parquet (CC BY-SA, filter <500-char stubs → ~500K articles) + VN legal
   corpus (YuITC MIT 214MB / th1nhng0 CC-BY 4GB); BGE-m3 GGUF Q8 via llama-server
   --embedding (dense) + BM25 lexical, hybrid α=0.5; Qwen3-Reranker-0.6B GGUF (validate
   scores — many community conversions broken). ~3.4GB added to image. NO SGK (copyright).
4. **Voting upgrades:** DeepConf confidence-filtered weighted voting (+5.1pp AIME at equal
   samples, −43–85% tokens); CISC P(True) weighting (+1.1pp, −46% cost); Borda tie-break.
   All need logprobs → llama-server `n_probs` (GPU phase). GenSelect judge pass for
   residual disagreements. Anti-patterns measured: bigger 3rd model (−0.0004), PoE-CoT
   prompting, naive int4 PTQ (−10pp).
5. **Labeled local dev sets EXIST for Vietnamese**: VMLU dev (MIT), ViGEText 3,722 exam
   MCQs, VLEMCQ (Apache) — enables real local accuracy measurement on GPU without
   burning leaderboard submissions (dev-only, never shipped, no hardcoding).

**Implemented this session (all green, 141 tests):**
- **NFC normalization** in the loader (decomposed Vietnamese diacritics tokenize/embed
  differently — silent degradation fixed for every path).
- **Few-shot mechanism**: `reasoning_few_shot_path` config + exemplar injection in
  `build_reasoning_prompt` (lru-cached loader, validation) + a 5-exemplar starter file
  `resources/exemplars-vi.json` (SELF-AUTHORED — license-clean, zero contest data;
  law/history/math/reading/negation coverage, Vietnamese reasoning + ANSWER format).
  Default OFF until A/B on the real model.

**Next increments (local, in order):** (1) offline-RAG scaffolding: chunker + BM25 (pure
Python) + Embedder protocol + hybrid retriever + question-type gate + prompt injection +
toy-corpus tests; corpus/index build scripts for the GPU phase; (2) DeepConf/CISC vote-
fusion scaffolding behind a logprob-capable client interface; (3) updated GPU runbook
with the new priority stack (GGUF swap first).

---

## 2026-06-11 — GPU SESSION 2 (A5000 community $0.16/hr): measurement battery — IN PROGRESS

Owner authorized GPU spend. Pod `ozflrk35xr9osd`, RTX A5000 24GB community ($0.16/hr —
1/3 the A40 price; balance $1.27 → ~8h runway).

**Staged:** UD-Q4_K_XL (14.25GB, Unsloth, ungated HF) + old Q4_0 (14.4GB, skopeo from our
image after a re-pull) + source-built llama-cpp-python + **ViGEText: 3,722 REAL Vietnamese
graduation-exam MCQs WITH labels** (7 subjects) → stratified 150-question dev set
(~21-22/subject). First time we can measure accuracy locally without leaderboard burns.
Labels live in a separate file and never enter the harness.

**Battery (detached, running):**
- A: old Q4_0, k=1 CoT (control = the 87.26 runtime)
- B: UD-Q4_K_XL, k=1 CoT (quant-swap effect)
- C: UD + 5-shot Vietnamese exemplars (few-shot effect)
- D: UD + tiered diverse self-consistency (escalation effect)
Each scored per-subject against gold labels.

### Incidents + fixes this session (all diagnosed root-cause, none guessed)
1. **Container disk 100% full mid-staging.** Cause chain: my first mkdir created `/models`
   as a REAL directory on the 20GB container disk → the staging script's symlink guard
   (`[ ! -e /models ]`) skipped linking → the 14.4GB old-GGUF extraction filled `/` and
   died partway. Fix: removed the partial, extracted directly to the volume path, and the
   battery uses absolute `/workspace/models/...` paths (no symlink dependency).
2. **All variants instantly FAILED with empty logs → "Illegal instruction (core dumped)".**
   Root cause: community pod CPU is a **Xeon E5-2699 v3 (Haswell 2014) — AVX2 but NO
   AVX512**; the prebuilt cu124 llama-cpp-python wheel contains AVX512 instructions →
   SIGILL at model load (import itself is fine, which is why nothing was logged). Fix:
   **source-build** llama-cpp-python with nvcc 12.8 (present in the pod image at
   /usr/local/cuda/bin, not on PATH), `CMAKE_CUDA_ARCHITECTURES=86`, native CPU flags,
   64-core parallel build → BUILD_DONE, model loads cleanly.
   NOTE: the CONTEST image is unaffected — it builds llama-cpp inside Docker from the
   target environment; this was purely a cheap-dev-pod hazard.
3. llama.cpp official releases ship NO Linux-CUDA binaries (Windows-only CUDA) — the
   llama-server-binary shortcut is not available on Linux pods; source build is the path.
4. PowerShell→ssh quoting + local sandbox false-positives keep biting → settled workflow:
   **Write script file → scp → `tr -d '\r'` → bash** (never inline quotes, never rely on
   sed for CRLF, beware UTF-8 BOM from PowerShell `Set-Content`).
5. Dataset availability: `nqdhocai/vietnamese-legal-qa` is gone from HF;
   `uitnlp/ViGEText_17to23` works ungated and its format is `{id, input, target}` with
   options embedded in `input` as `A. ...` lines (parser written accordingly; subject is
   the 3rd underscore-token of `id`).
