# MTP measured on real GPU — 2026-06-13 (RTX 3090 community, 26B-A4B Q4)

llama-server (`--spec-type draft-mtp`), pinned llama.cpp commit 597b6672, KV f16, contest-shaped
reasoning prompt (temp 0.8), 3 requests/config median.

| config | tok/s (median) | speedup vs baseline | draft acceptance |
|---|---|---|---|
| baseline (no MTP) | 138.7 | 1.00x | — |
| mtp_n1 | 177.9 | 1.28x | 0.79 |
| **mtp_n2** | **189.7** | **1.37x** (best) | 0.70 |
| mtp_n4 | 174.2 | 1.26x | 0.53 |
| mtp_n6 | 149.1 | 1.07x | 0.40 |

## Verdict: real but modest; does NOT clear the >=1.4x gate

- **MTP gives a genuine ~1.3-1.37x speedup** on this MoE model + 3090. Best at `--spec-draft-n-max 2`.
- **Below the self-imposed >=1.4x gate** (best 1.367x). The MoE caveat (llama.cpp issue #24266,
  the unsloth note) held: draft acceptance falls fast with n (0.79 -> 0.40) because the MoE
  early-stops / the drafter mispredicts; speedup peaks at n2 then declines. The 1.4-2.2x figures
  are best-case (dense models on a B200), not 26B-A4B MoE on a 3090.
- **`content_matches_baseline=false` is a temperature artifact, NOT proof MTP is lossy.** The
  benchmark ran at temp 0.8 (reasoning prompt) -> stochastic generation -> outputs never byte-match
  (baseline-vs-baseline would also differ). draft-mtp is lossless only under GREEDY decoding, so a
  temp=0 run is required to actually verify losslessness. The "fail" verdict is on this content
  check and is inconclusive here, not a real regression.

## Decision

MTP is a BORDERLINE Vong-2 time lever: a real ~1.37x but under the 1.4x bar, and it adds Docker
complexity (build/package llama-server + switch the runtime to the `local_server` provider).
Time is already safe (~1.6 h for 2000 q; with MTP ~1.2 h). Recommendation: do NOT ship MTP for
Vong-2 unless the owner wants the marginal time edge. The infra (entrypoint NEKO_LOCAL_SERVER_MODE
+ run_mtp_server.sh) is kept, off by default, for a future re-measure.

Artifacts: `data/q4results/mtp_logs/` (summary.txt, results.jsonl, run.log).
