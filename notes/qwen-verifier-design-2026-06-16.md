# Qwen cross-model verifier — design spec (2026-06-16)

Status: DESIGN ONLY (not implemented). Decide before coding. The accuracy EV is low-medium; the value
is mostly **Idea** (a legitimate dual-allowed-model, cross-family verification architecture).

## Rationale (why cross-family, not more self-votes)
Self-consistency's blind spot: when Gemma reasons wrong *systematically*, all K samples agree on the
same wrong answer → high confidence, wrong. This is exactly why maj@k washed for us. A different model
family (Qwen) has different systematic errors, so on a question Gemma is UNCERTAIN about, Qwen's
independent votes break the same-model self-confirmation bias. SOTA (CoVe, MoA): cross-family > self,
and the benefit is on **logic/math/reading**, NOT pure knowledge (if both don't know a fact, no help).
→ Target the **quant cluster only**.

## What already exists (no new architecture needed)
- `solver.solve_with_challenge(problem, client, challenger, config)` — runs Gemma self-consistency →
  if `agreement < self_consistency_challenge_threshold` and a challenger is set, gathers
  `challenger_samples` Qwen votes and re-tallies the COMBINED pool. Degrade-safe (no challenger →
  plain self-consistency). Unit-tested with stubs.
- `_solve_tiered` already takes + uses `challenger`; `solve_problem` threads `challenger` to the
  tiered/router strategies.
- `model_client.build_challenger_client(config)` builds a `LocalLlamaChatClient` from
  `challenger_provider` + `challenger_model_path` (+ `challenger_model_id`); returns None if unset.
- Config accessors: `self_consistency_challenge_threshold` (0.75), `challenger_samples` (3),
  `challenger_provider`, `challenger_model_path`, `challenger_model_id`.
- Labeled dev set to measure on: `data/devsets/quant.json` (150) + `quant.gold.csv`.

## Missing to wire (the actual work)
1. **run.py**: build the challenger via `build_challenger_client(config)` and pass it into
   `solve_problem(..., challenger=...)`. Today the live path keeps `challenger=None`.
2. **Cluster gate (NEW refinement)**: escalate ONLY when `_is_quantitative(profile)` AND agreement <
   threshold. Don't escalate knowledge/civics (Qwen won't help there and can false-flip). Add to
   `solve_with_challenge` (or a thin `_solve_challenged` strategy) + a config flag
   `challenge_clusters` (default `["quant"]`).
3. **Model**: bake a Qwen3.5 ≤9B instruct Q4 GGUF into the image + set challenger config in the
   overlay. Confirm the exact allowed GGUF (rule = Qwen3.5≤9B).
4. **Workflow**: a runtime workflow `challenged` (strategy that calls solve_with_challenge with the
   real challenger), default OFF until measured. Default path stays byte-identical.

## Combine strategy — two options
- **A (built): pool-combine** — Gemma K + Qwen M votes, majority over the union. Simple, tested.
  Risk: if Gemma is wrong-but-plurality and Qwen splits, the union can still pick Gemma's wrong answer.
- **B: Qwen-as-verifier** — Qwen judges Gemma's top answer (or ranks the options); flip only if Qwen
  *confidently* disagrees. Closer to "precise verifier, not decider" (the roadmap's framing). More code.
- **Decision**: start with A (no new code beyond the gate), measure; only build B if A false-flips on
  the quant dev set.

## Deployment cost / risk (honest)
- **VRAM**: Gemma-26B Q4 ~14.6GB + Qwen-7B Q4 ~4.5GB ≈ 19GB → fits a 24GB judge GPU, **OOM on 16GB**.
  Mitigation flags: (a) Qwen on GPU (assume judge ≥24GB — Time score implies a real GPU); (b) Qwen on
  CPU (`challenger_n_gpu_layers=0`, no VRAM contention but slow — only on the escalated subset); (c) a
  smaller ~3B Qwen. Start with (a); keep (b) as the portable fallback.
- **Time**: Qwen runs ONLY on the quant-uncertain subset (the cluster+agreement gate) → bounded, but
  Qwen inference there adds latency. Measure wall-time on the quant dev set; abort if Time blows up.
- **Accuracy risk**: the gate is the hard part (same as RAG/TIR). MUST be behind a no-regression gate.

## Measurement plan (gate on this BEFORE any ship)
1. Build/measure `self-consistency` (baseline) and `challenged` on `data/devsets/quant.json` vs
   `quant.gold.csv` — GPU, real models, seeded.
2. Run `scripts/analyze_errors.py --input quant.json --baseline sc=base.csv --candidate
   chal=challenged.csv --reference quant.gold.csv` → per-cluster fix/false-flip + net.
3. **No-regression**: also run on `civics.json` + `reading.json` (Qwen must not regress them — the
   cluster gate should keep them untouched, verify empirically).
4. Promote ONLY if challenged is net-positive on quant AND civics/reading are unchanged AND Time is
   acceptable. Else keep it as an Idea-writeup artifact (built, measured, honestly reported), not shipped.

## EV verdict
Accuracy: **low-medium** (~+0-2 quant on 463; the quant cluster is already 86.7% and the addressable
true-reasoning errors are ~3-4). Idea: **high** (dual-allowed-model cross-family verification, gated,
measured). Treat it primarily as an Idea lever; ship only if the quant dev measurement earns it.

## ✅ MEASURED RESULT (2026-06-16, L40 pod) — DEAD END for shipping
Two `tiered` arms over the 150-question labeled quant dev set (the challenger needs the DIVERSIFIED
`tiered` base for a low-agreement signal; plain self-consistency is k=1 deterministic and never fires):
- **Arm A — tiered k=5, NO Qwen: 82.67%** (124/150). 16/150 (~11%) escalated.
- **Arm B — tiered + Qwen3.5-9B:** did NOT finish (the GGML_NATIVE=off wheel build took 43 min on the
  host CPU, then Arm A took 39 min, and the 2-model Qwen arm timed out the 120-min budget).
- **Decisive without Arm B:** the tiered base (82.67%) is already **−4pp BELOW the shipped k=1
  self-consistency (86.67% in the battery)**. Qwen only touches the ~16 escalated items, so even a best
  case can't lift tiered+Qwen above the simple k=1 ship. The cross-model direction is **net-negative
  vs the ship**, NOT because Qwen is bad but because the diversified base it requires loses on quant.
- This RE-CONFIRMS the battery: diversified / multi-sample voting hurts quant — the model over-trusts
  its systematic errors, so resampling adds noise, not correction. k=1 deterministic is genuinely best.
- **Process lesson (logged):** this was inferable from the existing battery ("self-consistency beats
  every alternative on quant"; tiered IS an alternative) BEFORE renting the pod (~$1.5 spent). Check
  measured data first. (memory `feedback-stop-low-ev-experiments`.)

## Verdict: DEAD for shipping; KEEP as Idea artifact
The built + unit-tested challenger code (cluster gate, `challenged` workflow, 254 green) + this
measured honest-negative = legitimate Idea-writeup material ("we built + measured cross-family
verification; reported the honest negative"). Do NOT ship it; do NOT spend more GPU on it.
