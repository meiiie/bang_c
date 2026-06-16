# Dense reranker gate — overturns the BM25 "RAG-gate dead" verdict (2026-06-15, no GPU)

Owner asked to research RAG / real-time-knowledge deeper (option A, dev-only). This note records a
NEW, dev-validated (no GPU) result that **partially overturns** the prior conclusion in
`rag-oracle-dev-2026-06-15.md`. The prior verdict ("no cheap gate separates the slice") was true for
**BM25 (lexical)** gating. It is **NOT** true for a **dense cross-encoder reranker** — that gate is clean.

## What was tested (fully offline, CPU, no labels needed)
- Reused the real harness: `classify_problem` + `BM25Retriever` over the curated 4-chunk current-VN-2025
  corpus (`data/rag/current_vn_2025.jsonl`).
- Applied the REAL router precedence first (`_solve_router`): quantitative→TIR, reading→reading WIN
  over rag. So the gate only ever sees the **237/463 rag-eligible pool** (non-quant, non-reading).
  This already removes the long-passage BM25 false-positives (e.g. test_0350/0363) the prior note
  worried about — they are `kind="reading"` and never reach RAG in production.
- Gate model: **`BAAI/bge-reranker-v2-m3`** (568M, multilingual, in the allowed BGE-m3 family),
  torch CPU (dev-only; never shipped). Score = `max_chunk sigmoid(logit(question, chunk))`.

## Result — clean separation (the gating blocker is SOLVED for the dense case)
Reranker relevance on the 237-pool, top of ranking:

| qid | reranker | bm25 | note |
|---|---|---|---|
| test_0224 (Gia Lai số xã) | **0.9999** | 5.42 | genuine 2025-fact ✓ |
| test_0301 (tỉnh sáp nhập vào Gia Lai) | **0.9963** | 7.71 | genuine 2025-fact ✓ |
| test_0432 (sau 1/7/2025 công dân cần…) | **0.7108** | 3.44 | genuine current-admin ✓ |
| test_0329 (sau 1/7/2025 nộp hồ sơ khuyến mại) | **0.5356** | 5.26 | genuine current-admin ✓ |
| — cliff — | | | |
| test_0273 (hệ thống CHXHCN VN) | 0.0434 | 5.26 | correctly NOT fired |

- The BM25 top-scorers were **physics** (`test_0083`/`test_0395`, bm25=8.19 — ABOVE every real
  positive) and HCM-thought/economics questions sharing common words (cấp/phương/tỉnh). Under the
  reranker they **collapse to ~0** and leave the top-25 entirely. This is exactly the lexical-overlap-
  without-semantic-relevance failure a cross-encoder is built to fix.
- **Threshold sweep:** T=0.8 → fires 2 (both real), **0 false-positives**; T=0.5 → fires 4 (all four
  genuine current-2025-fact), **0 false-positives** among the 237 pool. The first non-relevant question
  only appears at T<0.05.
- **Correct abstentions (gate honesty):** `test_0254` (commune-level xã→xã) rr=0.0015 — the 4-chunk
  corpus has no commune merger data, so the reranker correctly refuses to fire (would need a bigger
  corpus, not a different gate). `test_0087` (2-tier count) never reaches the gate: it misroutes to the
  **quant** bucket ("bao nhiêu cấp" trips the calculation marker) — a separate classifier issue.

## Honest interpretation — what this does and does NOT prove
- **DOES:** the reason RAG was "dead" was net-negative injection from a gate that couldn't isolate the
  slice. A dense reranker gate isolates it cleanly (≈100% precision on the pool, recall = the corpus-
  covered current-fact questions). The gate is **principled and generalizable** (a general relevance
  model, not tuned to qids) → not overfit to the public 463. The blocker is removed.
- **Does NOT:** this is **gate precision, not an accuracy gain.** It shows the gate fires on the right
  questions; it does NOT prove injecting the corpus flips them wrong→right. That still needs ONE GPU
  A/B (Gemma+gated-RAG vs the 88.34 baseline, no-regression gate). Premise is plausible (these specific
  2025 facts post-date Gemma's training), but unproven until measured.

## Bounded upside (anti-overfit reality check — unchanged)
- The gate fires on ~4/463 ≈ **0.9%** of the public test (corpus has only 4 facts). Even if all flip,
  ≈ +0.5–0.9pp public. The private 2000 is multilingual + general → the VN-2025 slice is likely
  **smaller** there. Upside is real but small and **bounded by corpus coverage** — more upside needs a
  bigger current-facts corpus (commune mergers like test_0254, 2025 decrees like Nghị định 125/2025 in
  test_0404), each of which the reranker would then gate the same way.

## Shipping cost / tension (if pursued for the contest)
- Adds a reranker dependency (~2.3GB) + torch to a container we keep deliberately stdlib-lean, and a
  per-question reranker pass (Time-score tension; run on GPU + only on the rag-pool to bound it).
- BTC allows BGE-m3 / Qwen-Rerank, so it is compliant; pick the exact allowed model before shipping.
- The 88.34 image is LOCKED and safe; this is optional polish before 23/6.

## Recommendation
1. **Finding stands:** the dense-reranker gate is the first viable, principled knowledge lever — record
   it. It corrects (does not contradict the spirit of) `rag-oracle-dev-2026-06-15.md`: BM25 gate dead,
   dense gate clean.
2. **If owner chases it:** (a) expand `current_vn_2025.jsonl` with the high-frequency 2025 facts
   (province/commune mergers, key 2025 decrees) to widen coverage; (b) run ONE paired GPU A/B of
   gated dense-RAG vs 88.34 with a strict no-regression gate. Only ship if it wins net-positive.
3. **If not:** submission stays locked at 88.34; this is logged as "gate solved, upside small,
   GPU-confirmation pending." Dev artifacts (reranker, torch) are local-only, never committed/shipped.

## Sharpened upside after mapping the gated set to the locked 88.34 answers
Router-gated set at T=0.5 (non-quant, non-reading, reranker>=0.5) = **4 questions**:

| qid | reranker | baseline 88.34 | corpus-correct | verdict |
|---|---|---|---|---|
| test_0224 (Gia Lai #xã) | 0.9999 | **C (140) WRONG** | B (135) | RAG can FIX |
| test_0301 (tỉnh→Gia Lai) | 0.9963 | **B (Đắk Lắk) WRONG** | A (Bình Định) | RAG can FIX |
| test_0432 (1/7 cấp hành chính) | 0.7108 | C — already CORRECT | C | RAG can only RISK |
| test_0329 (hồ sơ khuyến mại) | 0.5356 | A — already CORRECT | A | RAG can only RISK |

- **Realistic upside = at most +2** (test_0224, test_0301): +2/463 ≈ +0.43pp public (→ ~88.77).
  Likely less on the multilingual private 2000.
- **Risk:** the 2 already-correct gated questions (test_0432, test_0329) can only stay neutral or
  be broken by injection. They are also the LOWER-relevance pair (0.54–0.71) vs the wrong-fixable
  pair (~1.0). So **raising the threshold to ~0.9 fires ONLY the 2 wrong-fixable questions** and
  drops the 2 at-risk ones — a principled high-precision setting (fire only when the corpus chunk is
  a near-exact answer match). Confirm the mechanism with the A/B before fixing T.

## GPU A/B RESULT (2026-06-15) — CLEAN WIN: +2 wrong->right, 0 regressions
Same Gemma Q4 runtime, same 4 gated qids, two arms (baseline reproduced the locked 88.34 EXACTLY
= 4/4 determinism check):

| qid | baseline | RAG | corpus-correct | verdict |
|---|---|---|---|---|
| test_0224 | C (140) WRONG | **B (135)** | B | RAG FIXED |
| test_0301 | B (Đắk Lắk) WRONG | **A (Bình Định)** | A | RAG FIXED |
| test_0432 | C correct | C | C | kept (no break) |
| test_0329 | A correct | A | A | kept (no break) |

- **Net +2 wrong->right, 0 regressions.** The mechanism is confirmed: gated RAG injects the corpus
  fact, Gemma corrects the two it mis-remembered (135, Bình Định), and leaves the two it already had
  right untouched (T=0.5 is safe; no need to raise to T=0.9).
- **Public 463 projection: 88.34 -> ~88.77** (+2/463 ≈ +0.43pp). The no-regression manifest (local)
  showed the router-gate fires on EXACTLY these 4, so the other 459 answers are byte-identical to the
  locked pred — the new pred.csv = 88.34 with two cells flipped, both wrong->right.
- Ops: 2nd pod (the 1st failed: my run_ab.sh missed `--allow-development-workflow`, since `rag` is a
  development-phase workflow). Prebuilt CUDA wheel SIGILLs on the old community CPU (known) -> gate
  caught it -> source build (GGML_NATIVE=off, now `$(nproc)`=64-way ≈ 25min). Pod auto-terminated.

## Remaining decision — SHIP vs BANK (upside small, touches a LOCKED submission)
- The lever is PROVEN and principled/generalizable, but +0.43pp on public; the multilingual private
  2000 likely has a SMALLER current-VN-2025 slice -> private upside probably < +0.43pp.
- Shipping requires putting a reranker INTO the offline container. Clean path = **BGE-reranker-v2-m3
  GGUF via the llama-cpp-python we already build** (rerank/embedding mode) -> NO torch, stays portable
  (GGML_NATIVE=off). Plus the curated corpus. Then rebuild the locked image, re-validate the 2000-
  robustness contract, re-run full 463 to confirm ~88.77, and (owner-gated) re-submit.
- Corpus has only 4 facts -> expanding it (commune mergers, 2025 decrees) widens coverage for more
  upside, each gated the same clean way.

## Expanded corpus + ship-backend research (2026-06-15, no GPU)
Owner reframed: target is the 2000 private; 463 is only an architecture probe; no 463-overfit; exact
facts (one wrong word poisons it). See memory `feedback-rag-architecture-not-463-overfit`.

- **Corpus expanded 4 -> 37 chunks** = the full verified 34-province 2025 reform map (28 prov + 6 city,
  cross-checked vs chinhphu.vn counts + internally consistent: 63 old -> 34 reconciled). Built from
  authoritative general sources, NOT the 463 questions. A web-summary hallucination ("Đồng Nai is a
  city / 30-4-2026") was caught and discarded.
- **Gate re-validated on the 37-chunk corpus:** fires on EXACTLY the same 4 reform questions
  (test_0224/0301/0432/0329), 0 new false-positives. Adding 33 province facts did NOT make any
  history/geography question fire -> the cross-encoder gate is STABLE and GENERALIZES (semantic, not
  lexical). This is the key architecture-validation result; it also proves NO overfit (general facts
  didn't manufacture 463 hits — the lever is honestly bounded by reform-question density ~0.9% of 463).
- **Magnitude is NARROW:** even with the full corpus, only ~4 reform questions in 463 (upside still +2).
  On 2000 (multilingual) the gain scales with reform-question density — expected modest (~+0.5-1pp).
- **Ship-backend decision — CROSS-ENCODER required, bi-encoder rejected:**
  - Cross-encoder (BGE-reranker-v2-m3): clean cliff (0.70 -> 0.10), T=0.5 = exactly 4, 0 false-pos.
  - Bi-encoder (BGE-m3 cosine): known 4 rank 1-4 but SOFT — first irrelevant question at 0.536 vs
    test_0329 0.547. No clean threshold (T=0.55 misses test_0329; T=0.5 adds 7 false-positives). Too
    mushy -> would inject noise on the 2000. So embedding-mode shipping (the easy llama-cpp path) is
    OUT; the cross-encoder's precision is what makes the gate generalize.
  - OPEN: ship a cross-encoder in the portable offline container. torch is OUT (CPU wheels need AVX ->
    SIGILL on old contest CPUs, same as the prebuilt llama wheel). Must run BGE-reranker GGUF via the
    same llama-cpp-python we already build (GGML_NATIVE=off) — feasibility of its rerank API is the
    next thing to verify. Fallback: llama-server `--reranking` via the existing `local_server` provider.

## Ship backend VERIFIED + P2 integration done (2026-06-15)
- **Pod probe (CPU-only, GGML_NATIVE=off): llama-cpp-python rerank WORKS and is portable.**
  `Llama(embedding=True, pooling_type=LLAMA_POOLING_TYPE_RANK)` on `bge-reranker-v2-m3-Q8_0.gguf`
  loaded with NO SIGILL and separated massively: a reform question scored logit ~+5..+7 vs an
  off-topic physics question ~-9..-11 (delta ~+16 -> sigmoid ~0.996 vs ~0). Any plain query+doc
  concatenation works (llama.cpp applies the reranker formatting under RANK pooling); the rank logit
  comes back as `create_embedding(...)["data"][0]["embedding"][0]`. So the cross-encoder ships via the
  SAME llama-cpp-python as Gemma — no torch, no AVX/SIGILL risk.
- **P2 integration (no-GPU, 244 tests green):** `rag_gate.py` now has two backends —
  `llamacpp` (ship; GGUF path) and `transformers` (dev; HF id) — both lazy-imported, both degrade to
  `None`->RAG-off if unavailable. Config: `rag_reranker_backend` (default `llamacpp`),
  `rag_reranker_n_ctx`, `rag_reranker_n_gpu_layers` (default -1). Default 88.34 path byte-identical;
  package imports stay torch-free. The logit->sigmoid->max extraction is unit-pinned to the probe.
- **Remaining for ship (owner-gated, not rushed):** (1) ONE full pod run of the REAL ship config
  (Gemma + `rag_gate=reranker, backend=llamacpp` + the GGUF + the verified corpus) on the 463 to
  confirm end-to-end gating + the +2 via the actual path (not forced `--workflow rag`); (2) bake GGUF
  + corpus into the image, set config; (3) re-validate 2000-robustness; (4) Docker push + leaderboard.
- **Corpus growth (owner's "real-time, current-law" idea):** YES but disciplined — only verified
  DELTA facts (2025-2026 changes the model is stale on), NOT a general encyclopedia; current-as-of-
  build (offline can't be real-time); re-validate the gate stays 0-false-positive after each growth.

## Law-corpus expansion A/B — NET NEGATIVE (−2): bigger corpus HURTS (2026-06-15)
Owner approved expanding to a general current-law corpus + an A/B. Built `combined_2026.jsonl` =
37 reform chunks + 27,031 chunks from `undertheseanlp/UTS_VLC` 2026 in-force split (306 laws, MIT,
validated vs vbpl.vn), chunked on Điều boundaries. Gate re-validated (sampled): recall UP (9/32 GAP
fire vs 4) but precision DOWN (~7% false-positives — environmental-SCIENCE questions fire on
environmental-LAW chunks, and they score HIGHER (0.82-0.87) than genuine law fires (0.54), so a
threshold can't separate them).

GPU A/B (pod-gated full 463 → 31 gated; Gemma baseline vs RAG(combined) on the gated set; codex-9374
oracle): **FIXED 2, BROKE 4, NET = −2.** The big corpus:
- Broke correct answers via false-positives (test_0223 urban/science: C→H).
- CROWDED OUT the reform facts — test_0301 went A (correct, with the clean 37-chunk corpus) → D
  (wrong, with the 27k corpus): law chunks displaced the reform chunk in BM25 retrieval.

**Verdict: the clean reform corpus (+2, 0 false-positives) BEATS the big law corpus (−2).** More
facts ≠ better; a large diverse corpus adds more noise than signal. The honest RAG ceiling is **+2
(~88.77) with the SMALL clean corpus**; expanding HURTS. Earlier "+4-6" guess was WRONG.
Dev artifacts `data/rag/uts_vlc_2026.jsonl`, `data/rag/combined_2026.jsonl` kept local, NOT shipped.

## EVIDENCE STATE — what is PROVEN vs PROJECTED (be precise; 2026-06-15)
- **PROVEN (Gemma GPU A/B):** the ORIGINAL 4-chunk reform corpus → **+2 wrong→right** (test_0224 C→B,
  test_0301 B→A), **0 regressions**; the baseline arm reproduced the locked 88.34 EXACTLY on those qids.
- **STRONG no-GPU evidence for the 37-chunk corpus** (the current `current_vn_2025.jsonl`, which
  superseded the 4-chunk file): BM25 retrieves the SAME correct Gia Lai chunks #1–2 for test_0224
  (bm25 22.76, has "135") and test_0301 (bm25 9.23/8.58, both name "Bình Định"); the reranker gate
  fires on exactly the same 4 (1.000/0.997/0.968/0.703). So the 37-chunk corpus injects the SAME
  correct facts → +2 is expected to hold — but the 37-chunk **Gemma flip is NOT directly A/B-confirmed**.
- **NOT CONFIRMED:** (a) the 37-chunk Gemma flip (only retrieval/gate-confirmed); (b) the actual
  leaderboard score — **"88.77" is an ARITHMETIC PROJECTION** (88.34 + 2/463×100 = 88.77), NOT a
  measured leaderboard number. To confirm: one Gemma A/B on the 37-chunk corpus + a leaderboard submit.
- **DISPROVEN (Gemma GPU A/B):** the 27k law corpus → **−2** (false-positives + law chunks crowd out
  the reform chunks; test_0301 went A→D).
- **Net honest statement:** "the proven RAG lever flips +2 specific reform questions to their
  corpus-correct answers; projected ~88.77 on the 463, pending a 37-chunk Gemma A/B + leaderboard
  confirm. On the multilingual private 2000 the gain is likely smaller (fewer reform questions)."

## SHIP DECISION (recommended): clean reform corpus + reranker gate, +2, ~88.77 (projected)
The proven, safe configuration is the SMALL `current_vn_2025.jsonl` (37 chunks) + reranker gate
(0 false-positive, +2 wrong→right). The llamacpp ship backend is verified (probe). Remaining: bake
GGUF + the 37-chunk corpus, one full-463 end-to-end pod run to confirm ~88.77 via the real path, then
owner-gated Docker push + leaderboard. Do NOT ship the law corpus.

## (historical) GPU A/B plan — was IN PROGRESS
Controlled, same Gemma Q4 runtime as the 88.34 image, SAME 4-question gated input, two arms:
- ARM A `--workflow self-consistency` (must reproduce the locked 88.34 answers = determinism check).
- ARM B `--workflow rag` forced + current_vn_2025 corpus via `.neko-core/config.json`.
The reranker gate ran LOCALLY (it only selects the qids); the pod is torch-free. Orchestration
`Temp/pod_ab/ab_launch.py` (cheap-first 3090, auto-`podTerminate`). Reads: is RAG flipping
test_0224/0301 wrong->right, and does it leave test_0432/0329 intact? Then choose T (0.5 vs 0.9).
**PAUSE for owner before any leaderboard submit.**

## Repro
`PYTHONPATH=src` + global Python (torch CPU `--user`, dev-only). Script run inline; reranker
`BAAI/bge-reranker-v2-m3`; corpus `data/rag/current_vn_2025.jsonl`; input
`Downloads/public-test_1780368312.json`. ~187s model load + ~2.5s/q CPU over 237 = ~13 min total.
