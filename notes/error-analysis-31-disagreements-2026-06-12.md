# Error-structure analysis of the 31 disagreements (2026-06-12)

Multi-agent workflow (56 agents, 1.8M tokens): for each of the 31 public-test questions where
the shipped Gemma-26B pred (88.55) disagrees with the 91.79 frontier reference, an independent
judge re-solved + classified, then a skeptical verifier confirmed recoverability. Goal: is the
~88.98 advancement bar reachable offline, and by which lever?

## Result

- **Verdict split:** ref(frontier)-right **27**, gemma-right **3**, both-defensible **1**. → On
  these disagreements Gemma is genuinely wrong ~27 times; the gap is real, not just noise.
- **Categories:** knowledge_gap 13, reasoning_or_calc_error 10, defective_or_ambiguous 6, negation_or_parse 2.
- **Confirmed recoverable (skeptic-verified): 16/463** → optimistic ceiling **+3.46pp**; the bar
  needs only ~+0.43pp (~2 net flips). **bar_8898 = REACHABLE in principle.**
- Recoverable breakdown: **10 reasoning/calc**, 4 knowledge (in-weights), 1 negation, 1 ambiguous.
- Recoverable qids: test_0061, 0063, 0068, 0109, 0110, 0133, 0173, 0247, 0258, 0269, 0313,
  0318, 0368, 0441, 0452, 0454.

## The key insight (decides the lever)

The recoverable set is **deterministic calculation + careful reasoning**, NOT a second model's
unique knowledge. Examples:
- **test_0063** Henderson-Hasselbalch: 5.00+log(0.1/0.2)=4.70 → 4.75 (B); Gemma's 4.50 = a log
  arithmetic slip.
- **test_0110** induction motor: n_s=120·50/4=1500, n=1500·0.98=1470 rpm (A); Gemma's 735 = a
  pole/÷2 error.
- **test_0061** econ-geography (urbanization driven by industrialization); **test_0109** a
  "trước"/temporal-qualifier parse; **test_0068** Augustine doctrine.

These are **exactly what the already-built TIR (Python exec) + CoT/self-consistency path
targets** — NOT what a Qwen3.5 cross-model adjudicator uniquely unlocks. Multiple verifiers
flagged the Qwen cross-vote as a coin-flip or a backfire risk (it could false-flip some of the
27 ref-right items → regressions).

## Recommendation (from the workflow, well-supported)

1. **Do NOT spend a GPU trial on the Qwen adjudicator.** Low upside, real regression risk.
2. **The honest path to 88.98, if pursued, is the EXISTING TIR/router path** (built, currently
   OFF). Earlier "TIR ruled out" was the misleading ViGEText *proxy*; this analysis on the REAL
   463 shows TIR targets the actual recoverable errors. The clean test: one GPU run of the
   `router` strategy on the real 463 vs the 88.55 baseline — net-positive only if the calc
   recoveries outweigh any false flips on the 27 ref-right items. Measure before shipping.
3. **13 knowledge_gap items are unrecoverable offline** (VN-2025 admin reforms, hyperlocal
   trivia, exact regulatory counts) — confirms 88.55 is near the honest offline ceiling.
4. **Default recommendation: lock 88.55, pour effort into Vòng-2** (MTP time lever + bulletproof
   Docker + Idea doc). Only chase 88.98 via a single cheap `router`-on-463 measurement if the
   owner wants the advancement margin.

Raw per-question judgments: `notes/_error_analysis_findings.json` + workflow transcript.
