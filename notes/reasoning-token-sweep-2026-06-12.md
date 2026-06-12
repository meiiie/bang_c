# 26B reasoning_max_tokens sweep — 2026-06-12

Real GPU run on a rented RTX 4090 (24 GB, SECURE), Gemma-4 26B-A4B QAT Q4_0 GGUF on
`llama.cpp`, the shipped config (safety lever ON, self_consistency k=1, constrained-repair
ON). Full 463-question public set at three caps. Pod terminated after pull.

## Time (measured, 463 questions)

| reasoning_max_tokens | wall-clock | s/q | private 2000 est. |
|---|---|---|---|
| 768  | 1272 s (21.2 min) | 2.75 | ~1.53 h |
| 1280 | 1327 s (22.1 min) | 2.87 | ~1.59 h |
| 2048 | 1357 s (22.6 min) | 2.93 | ~1.63 h |

The dial is **nearly flat**: 2048 is only +85 s (+6.7 %) over 768 across 463 questions,
because the MoE finishes most questions *before* the cap binds. Raising the cap costs
almost no time.

## Accuracy proxies (no official gold; agreement, not leaderboard)

Agreement vs the 91.79 hand-solved frontier reference (higher ≈ closer to truth):

| config | agreement vs 91.79 ref |
|---|---|
| 768  | 92.01 % |
| 1280 | 92.87 % |
| 2048 | **93.09 %** |
| (prior 88.55 probe) | 93.30 % |

Monotonic: more tokens → marginally closer to the frontier reference (768→2048 = +1.08 pp).

Stability / flips:
- 768 vs 2048: 17 flips (3.7 %); 1280 vs 2048: 14 (3.0 %); 768 vs 1280: 7.
- 2048 sweep vs the prior 88.55 probe: 94.38 % agree (26 differ) — consistent with the
  proven ~88.55 band. The 26-answer gap is **run-to-run llama.cpp variance** (different
  GPU/build, k=1 with temp>0): ~5.6 %, which *exceeds* the inter-config gap.

## Decision — keep reasoning_max_tokens = 2048 (current default)

1. **Time is not the constraint.** Every cap runs 2000 private questions in ~1.5–1.6 h;
   the 10-pt time score is safe at full token depth. There is no time pressure forcing a
   lower cap.
2. **2048 is weakly dominant and free.** It is monotonically closest to the frontier
   reference, at a negligible +6.7 % time cost. Lowering the cap would trade a small
   accuracy edge for almost no time saving — a bad trade.
3. **The dial is flat by design.** 26B-A4B is an early-stopping MoE, so the Time↔Accuracy
   knob barely moves. No tuning needed; the shipped default is already the right point.

Caveat (honesty): agreement-with-reference is not leaderboard accuracy, and single-run
variance (~5.6 %) is larger than the 768↔2048 gap. So 2048 is the safe, free choice — not
a proven leaderboard lift over 768. The final number remains whatever the leaderboard says
for the shipped config (~88.55 band).

## Operational confirmations from the same run

- **Docker-CMD smoke PASSED on real GPU**: the exact contest entrypoint args produced a
  valid `/output/pred.csv` (header `qid,answer`, all-letter answers, contract 40/40,
  harness_score 100.0) with the new bulletproof-contract code.
- 26B speed vs 31B: **~2.9 s/q vs ~90 s/q** (~30× faster) — confirms 26B as the contestant.
