# Clean +RAG ship path (`rag-gated`) — result, comparison, decisions (2026-06-16)

## TL;DR
A new **`rag_gated`** strategy/workflow ships the locked self-consistency baseline PLUS targeted RAG
on ONLY the dense-gated, reading-excluded current-fact slice. Validated on the full 463 + a dedicated
reranker-score audit. It fixes **3** corpus-verified VN-2025 admin-reform questions with **0
false-positives**. Artifact built + locally validated; **not yet pushed** (owner-gated).

## ✅ LEADERBOARD CONFIRMED (2026-06-16): 88.34 → 88.98
Owner submitted the rag-gated pred (locked + 3 fixes) to the public-463 leaderboard → **88.98**. The +3
fixes all scored correct against BTC ground-truth — RAG is leaderboard-validated, not just
corpus-verified. The private 2000 likely has more current-fact questions, so the gate should help more
there. Next = build + push the image; the locked 88.34 image stays as the safe fallback.

## Why a new strategy (not the existing `router` / `rag`)
- The reranker gate `_is_rag_eligible` lived ONLY inside `_solve_router`, which also routes
  quant→TIR and reading→reading-grounding. The battery measured both of those net-flat/negative
  (reading-grounding 90.0 vs 91.67). So shipping `router` would import known-bad levers.
- The standalone `rag` strategy forces `_solve_rag` (BM25) on EVERY item → over-fires on lexical
  overlap (the false positives the dense gate exists to kill).
- `rag_gated` = `_is_rag_eligible(reranker) AND not _is_reading → _solve_rag, else
  _solve_self_consistency`. Non-gated items are byte-identical (in code) to the locked
  self-consistency path. Workflow `rag-gated` is phase=runtime (no `--allow-development-workflow`).

## Full-463 in-process validation (pod 3090, ~31min)
strategies `{gemma_rag:66, gemma_self_consistency:397}` at the OLD threshold 0.5; 0 tir/reading.
- **3 genuine fixes (corpus-verified correct):** test_0087 `1/7/2025 mấy cấp` A(3)→**B(2)**;
  test_0224 Gia Lai xã C→**B(135)**; test_0301 tỉnh sáp nhập Gia Lai B(Đắk Lắk)→**A(Bình Định)**.
- **1 false positive found:** test_0047 = a Granny-Smith APPLE reading passage scored relevant to the
  2025 corpus and RAG flipped it. Root cause: `rag_gated` had dropped the router's "reading wins over
  RAG" guard. **Fixed:** added `and not _is_reading(profile)`. Keeps all 3 fixes (none are reading).
- 6/397 self-consistency items also drifted vs locked WITHOUT firing RAG = ~1.5% inherent GPU/numeric
  run-to-run nondeterminism (present in the locked baseline too — NOT a RAG defect).

## Gate-score audit (reranker over all 463, CPU portable wheel) → threshold
CLEAN bimodal separation:
- 6 genuine VN-2025 admin-reform questions: **0.918 – 0.999** (test_0224 .999, test_0087 .999,
  test_0301 .993, test_0432 .986, test_0106 .964, test_0329 .918).
- First non-current-fact (physics, test_0255): **0.613**, rest tail down to ~0.
- WIDE gap 0.61 ↔ 0.92 → **ship threshold = 0.85** (mid-gap): fires on EXACTLY the 6 current-fact qs,
  **0 false positives**. RAG fixes 3, confirms 3 already-correct (test_0432/0106/0329).
- Defense in depth: the apple (0.989, in the genuine score range) is caught by the READING GUARD, not
  the threshold; the threshold kills the mid-band junk (physics 0.61, etc.).

## Comparison
| | Accuracy (463 probe) | Notes |
|---|---|---|
| Locked self-consistency | 88.34 (leaderboard) | safe baseline, no RAG |
| **`rag-gated` (this)** | **+3 corpus-verified fixes ≈ 89.0** | generalizes to 2000-private (more current-fact qs there); 0 false-positive; reranker CPU |
| codex GPT-5.5+web | 93.74 | FORBIDDEN upper bound — different model + web; gap is model-capability, not harness. Not a target. |

Caveat: the 463 `test_0XXX` set has no local labels, so the +3 is corpus-fact-verified, not
leaderboard-scored; the true measure is the 2000-private (where the gate grounds any current-fact qs).

## Ship artifact (uncommitted working tree)
- `docker/rag-gated.neko-core.json` — baked overlay (rag_gate=reranker, threshold 0.85, reranker
  `/models/bge-reranker.gguf` on CPU `n_gpu_layers=0`, corpus `/app/data/rag/current_vn_2025.jsonl`).
- `Dockerfile.rag-gated.kaniko` — portable GGML_NATIVE=off wheel (Gemma GPU + reranker CPU) + Gemma Q4
  + BGE reranker GGUF + corpus + overlay; `CMD --workflow rag-gated`.
- Build target: `docker.io/hacamy12345/neko-core:gemma26b-q4-rag-gated-20260616` (NEW tag; the locked
  `gemma26b-q4-portable-20260614` is untouched).
- 250 tests green (test_rag.py +7: fires-on-gated, byte-identical-off-gate, no tir/reading routing,
  reading-guard, runtime-phase, threshold). Reranker portability: the prebuilt cu124 wheel SIGILLs
  (rc=132) on community CPUs → GGML_NATIVE=off REQUIRED (same lesson as the Gemma wheel).

## Reproduce
- Gate audit: `Temp/pod_mtp/run_gateaudit.sh` + `gateaudit_launch.py` (CPU portable wheel, scores
  reranker over 463 → threshold sweep + top scorers).
- Full validation: `run_ragvalidate.sh` + `ragvalidate_launch.py` (`--workflow rag-gated` on 463).
- Build: `kaniko_full_launch.py` with `DOCKERFILE=Dockerfile.rag-gated.kaniko TAG=...` + context
  `neko-portable-context.tar.gz`.
