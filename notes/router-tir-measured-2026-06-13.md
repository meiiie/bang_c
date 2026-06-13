# router / TIR measured on the real 463 — DEAD (2026-06-13)

GPU run on a rented RTX 3090 (community), Gemma-4-26B-A4B QAT-Q4_0, same shipped config
(safety lever, 2048 tokens). The code on the pod was the **overfit-removed working tree**: a
guard asserted `PRINCIPLE_RULES == ()` and `CALCULATION_DECISION_RULES == ()` before running
(it passed), so router used only the general calculation-formula adjudicators + TIR (Python
execution), no per-question hard-codes. Baseline self-consistency and router were run on the
same pod/model for a clean delta.

## Result — router/TIR is much WORSE than self-consistency

| run (same pod, same model) | agreement vs 91.79 reference | time (463) |
|---|---|---|
| self-consistency (shipped path) | **92.66 %** | 1652 s (27.5 min) |
| router / TIR | **83.37 %** | 1884 s (31.4 min) |
| delta | **−9.29 pp** | — |

Router changed **53** answers vs self-consistency. On those 53: router matched the reference
only **4** times while self-consistency matched it **47** times → **NET −43**. TIR's
mis-routing and wrong generated Python OVERRIDE correct self-consistency answers far more
often than it recovers anything.

(The self-consistency baseline at 92.66 % agreement corresponds to the same ~88.55 leaderboard
band; the prior probe was 93.30 % — the 0.64 pp difference is run-to-run variance. The 92.66 %
is a proxy-agreement number, NOT a leaderboard score.)

## Conclusion — the general TIR/router path is dead too

This refutes, on a real measured run, the error-analysis hypothesis that TIR could recover the
quantitative items. The false-flip cost (47 correct answers overridden) vastly outweighs the
recoveries (4). So:

- **All three accuracy levers are now measured DEAD:** bespoke deterministic rules (overfit,
  removed), maj@k diverse voting (wash), and general TIR/router (−9.29 pp here).
- **Keep the shipped `self_consistency` path (≈88.55).** Do NOT route to TIR.
- 88.55 is near the honest offline ceiling; the gap to the ~88.98 bar is knowledge-bound, not
  technique-addressable. Clearing it would rely on run-to-run variance (±2–3 pp per submission),
  not a reliable lever.

Artifacts: `data/q4results/router_pred_sc.csv`, `router_pred_router.csv`, `router_timings.txt`
(gitignored). Why TIR over-fires: the router's `_has_quantitative_signal` classifier routes
many non-numeric items to TIR, and the model's generated Python frequently solves the wrong
quantity, so the deterministic override replaces a good CoT answer with a wrong computed one.
