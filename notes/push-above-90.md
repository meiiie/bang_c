# Push 87.26 → 90+ (research brief for the next phase)

> **STATUS UPDATE 2026-06-11:** target revised to **93+**. Cited deep research done
> (`research-93-cited-reports.md`) and **all model-independent mechanisms are BUILT and
> stub-tested** (127 tests green): seeded temp>0 diverse sampling (T=0.8/top_p=0.95/
> top_k=64 per Gemma guidance), cyclic choice-rotation position-bias debiasing, the
> `tiered` strategy (agreement-gated escalation, ESC/MoT pattern), invalid-sample repair,
> and cross-model challenger pooling wired through `run.py` (config-gated, allowlist-
> enforced). Remaining work is GPU-bound — see the runbook at the bottom.

## ⚠️ Evidence-backed AVOID list (from the cited research — do NOT do these)
- "Are you sure?" self-verification rounds: −1…−17pp (sycophantic flips).
- Generative elimination prompting as the default: −5…−14pp (worst on negation items).
- Replacing CoT with pure logprob/cloze scoring: ≈−10pp on our own data (77.11 vs 87.26).
- Whole-sequence logprob as a confidence signal (length-biased); use answer-letter
  probability or agreement instead.

Date: 2026-06-11. Baseline to beat: **CoT k=1 = 87.26** (public, 463). Gap to 90 ≈ **+13
correct answers** (404→417 of 463). Owner's read: competitors are well above 90, so we need
a *substantial* jump, not polish.

## The mindset shift
Accuracy (80 pts) is now paramount; time (10 pts) is secondary but not free. The single
biggest unused lever is that **CoT k=1 runs at temperature 0 → one deterministic path**. The
proven way to lift reasoning accuracy is to explore **multiple diverse paths and vote**
(self-consistency) and **a second independent model** (ensemble) — both allowed, both
currently untapped. Make these affordable with **tiering**: cheap single-CoT for easy items,
expensive ensemble only for the uncertain tail. Calibration (agreement) tells us which.

## Levers, ranked by accuracy-per-effort

### 1. Self-consistency at temperature>0 (HIGHEST expected impact)
Today k=1 @ temp 0 = one path. Change: sample **k=5–10 reasoned paths at temp ~0.6–0.8**,
majority-vote. This is the classic self-consistency boost (Wang et al.) — typically +3–8% on
math/reasoning, exactly the calculation cluster where CoT already changed 38% of answers.
- **Enabler (code):** `local_client.py` hard-codes `temperature=0.0, top_p=0.1`. Add a
  `temperature` (and top_p) parameter threaded from config → the reasoning path uses temp>0
  for sampling. Add config keys `reasoning_temperature` (e.g. 0.7), keep k from
  `self_consistency_samples`. The voting/calibration machinery already exists.
- **Bonus:** with diverse samples, the agreement confidence finally becomes *real* (it was
  always 1.0 at temp 0) → drives tiering (#4) and tells us where we're weak.
- **Cost:** k× the single-CoT time. Mitigated by tiering.

### 2. Cross-model ensemble: Gemma-4-26B + Qwen3.5 (HIGH)
Two different architectures catch different errors. Run both, vote (or use `solve_with_challenge`,
already written). Qwen3.5≤9B is small/fast; A40 48GB holds both (26B-Q4 ~15GB + Qwen-8B-Q4 ~5GB).
- Allowed by the rules. Expected +2–5% (ensembles reliably help), especially where one model
  has a blind spot.
- **Enabler:** wire a second provider/model client; `solve_with_challenge(primary, challenger)`
  is ready — needs the CLI to build the 2nd client from config.

### 3. Tiering (makes #1+#2 affordable, protects the 10 time-pts)
Single CoT first → if agreement < τ (uncertain), escalate to k>1 self-consistency + cross-model.
Most items finish cheap; only the hard tail pays. Tune τ so the average time stays sane for 2000q.

### 4. Stronger reasoning prompt (MED)
Few-shot CoT (1–2 worked examples), an explicit "re-check your arithmetic" step, "show each
step" for calculation. Cheap, can add +1–3%. Risk: longer prompts = more tokens.

### 5. Fix the 7 truncation fallbacks (LOW-MED, easy)
7/463 still hit the 2048 cap or ramble. Raise to 3072/4096 for long items, or detect "no
ANSWER: line" → one retry with a higher cap / "answer now" nudge. Up to +1.5%.

### 6. Targeted error study (ongoing)
We have no per-question gold (leaderboard gives only the aggregate). Proxy: **strategy
disagreement** = likely-hard items. Compare CoT vs (temp>0 vote) vs (cross-model) on the 463;
where they disagree is where the points are. Focus prompt/tier work there.

## Recommended experiment order (each: implement → local check → GPU run → leaderboard)
1. **temp>0 self-consistency k=5** (lever #1) — likely the biggest single jump. Submit.
2. **Tiering** (lever #3) so k=5 is affordable; measure time.
3. **Cross-model challenger** (lever #2) on the uncertain tail. Submit.
4. **Prompt few-shot + self-check** (lever #4). Submit if it beats current best.
5. **Fallback fix** (lever #5) — fold in anytime.

## Discipline (important)
- **Leaderboard submissions are the only real accuracy signal** and may be rate-limited.
  Pre-filter locally: no regression on the gold suite, answer stability, fewer fallbacks,
  sane agreement distribution — THEN submit the most promising.
- Every change keeps the contract valid, diacritics, offline runtime; tests green.
- Re-package the image (crane, fast) only after a change wins on the leaderboard.
- Measure time on every accuracy change (the 10 time-pts).

## Infra notes for the GPU runs
- Provision A40/A6000 48GB; pull the model from `hacamy12345/neko-core:gemma26b-q4` via skopeo
  (no HF token); for Qwen, find an allowed Qwen3.5≤9B GGUF (or extract from an image if gated).
- The full 463 CoT run is ~35 min on A40; budget accordingly. Terminate promptly.
- See `notes/worklog.md` (RunPod A40 section) for the exact provisioning + skopeo + run recipe.

---

## GPU-phase runbook (next session — everything below needs the real model)

Budget note: RunPod balance ≈ $1.31 after the first test; an A40 is $0.44/hr and the
experiment matrix below needs ~2–4 hours → **top up the RunPod account first** (~$5–10).

1. **Provision + stage (per the worklog recipe):** A40/A6000, skopeo-extract the Gemma GGUF
   from `hacamy12345/neko-core:gemma26b-q4`, pip install cu124 llama-cpp, scp this branch.
   NEW: also download a **Qwen3.5 ≤9B instruct GGUF (Q4_K_M)** — Qwen GGUF repos on HF are
   normally ungated (`huggingface_hub.hf_hub_download`, no token). Verify the exact repo id
   at run time; set `challenger_provider=local_llamacpp`, `challenger_model_path=...`,
   `challenger_model_id=qwen3.5-...` in `.neko-core/config.json` on the pod.
2. **Seed determinism smoke (cheap, do first):** same question, same seed, temp 0.8 → twice;
   confirm identical output (llama.cpp seeded sampling; CUDA batching caveat noted in the
   research). If unstable, document and accept near-determinism.
3. **Experiment matrix on the 463 (one run each, ~35–60 min/run):**
   a. `tiered` (tier1=2, total=5, no challenger) vs the k=1 baseline answers → measure:
      gold 5, tier-1 unanimity rate, answer diff vs 87.26 run, wall-clock.
   b. `tiered` + Qwen challenger (challenger_samples=3) → same measures + how often the
      challenger flips the pooled vote.
   c. If time: tier1=3/total=8 (research's k dial), T=1.0 variant.
4. **Letter-logit readout (rank-1 lever, ~free):** implement against real llama.cpp via the
   low-level API (`llm.eval(tokens)` then read final-position logits over the letter tokens
   after a forced "ANSWER:" suffix — do NOT use logits_all=True). Gives extraction-proof
   answers + an MSP confidence to sharpen tier-1 routing.
5. **Pick the winner locally** (gold + stability + unanimity-rate sanity), **owner submits
   to leaderboard** (one submission per validated candidate, never blind).
6. If the winner uses the challenger: rebuild the image with BOTH GGUFs baked in (size
   check!), smoke the container offline, update Dockerfile/entrypoint defaults, repackage
   via the crane recipe, and re-validate `--check-submission`.
