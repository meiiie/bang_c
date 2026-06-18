# Fine-tune verdict — SFT on available data does NOT beat the base (2026-06-18)

**TL;DR:** Two decisive QLoRA runs on Qwen3-4B-Instruct-2507 measured on the 450-q labeled proxy
(self-consistency k=1). Off-distribution data hurts; all available in-distribution data is exactly
neutral. **Conclusion: ship the un-fine-tuned base (image v0.7.1, leaderboard 83.59). The fine-tune
lever is exhausted on current data; the only path forward is more broad-subject MCQ data.**

## Baseline (un-fine-tuned, k=1, 450 proxy)
OVERALL **80.22%** — quant 73.91 / civics 78.67 / reading 85.41.  (private leaderboard 83.59)

## Experiments
| run | training data | overall | quant | civics | reading | verdict |
|-----|---------------|---------|-------|--------|---------|---------|
| baseline | none | 80.22 | 73.91 | 78.67 | 85.41 | — |
| **v1** | 4323: vmlu-mcq 823 + math 2311 + traffic/legal 1189 | **75.78** (−4.44) | 59.13 (−14.78) | 78.67 (0) | 83.78 (−1.63) | FAIL |
| **v2** | 823 vmlu-mcq only (all available in-dist MCQ) | **80.22** (+0.00) | 72.17 (−1.74) | 78.00 (−0.67) | 87.03 (+1.62) | NEUTRAL |

Both: QLoRA r16/alpha32 4-bit, 1 epoch, merge→F16 GGUF, harness self-consistency on the 450 proxy.
Each run was train→merge→convert→portable-wheel→eval on one rented GPU (ssh-observable; pod auto-terminated).

## Why
1. **Math (free-form) destroyed quant MCQ** (−14.78 in v1). Removing it recovered quant 59→72. The
   open-form math/legal answer format conflicts with the contest's MCQ "ANSWER: X" task.
2. **Legal QA did not transfer to civics** (flat both runs) — wrong task shape (open QA vs MCQ).
3. **The base is already at the ceiling.** v2 used *all* available in-distribution data (823 VMLU MCQ,
   ~56 subjects) and landed *exactly* on baseline. SFT can't squeeze more from this thin, well-matched set.

## Data reality (the real bottleneck)
- Broad-subject MCQ (the only in-distribution shape) = **1038 rows total** (823 train + 215 eval) from VMLU.
- The rest of the prepped ~103k is legal (89k, narrow enterprise law) + math (12.5k, free-form) — both
  off-distribution for the contest's broad MCQ.
- To beat the base, we need MORE broad MCQ. Candidate sources blocked (ViEduQA / ViLegalTF → HTTP 401) or
  require synthetic-MCQ generation from the corpus (quality-risky; needs validation). **Owner decision.**

## Recommendation
- **Submission stands: un-FT base, v0.7.1.** Fine-tuning touched nothing in the shipped image.
- Do NOT spend more GPU on SFT variants of the current data (proven wash).
- If pursuing FT later: (a) unblock/scrape more broad Vietnamese MCQ, or (b) generate + validate synthetic
  MCQ from the legal/math corpus, then retrain MCQ-heavy. Both are data-collection tasks, not training tweaks.

Detail log: `Temp/pod_mtp/FT_RESULTS.md`. Mixers: `data/finetune/processed/train_v1_mix.jsonl`,
`train_v2_mcq.jsonl` (823 MCQ filtered from v1).
