# RAG oracle dev experiment (no GPU) — 2026-06-15

Re-opened the knowledge-injection lever after the 88.34-vs-93.74(codex) diff showed the loss cluster
is **stale current-VN admin/law facts** (2025 reorg: 2-tier model, 63→34 provinces, Gia Lai+Bình
Định=135 xã, căn cước/BVMT specifics). Goal: dev-validate (no GPU) whether targeted RAG with a
*current* corpus can recover them — the prior "targeted RAG ruled out" used a STATIC statute corpus
that misses the 2025 facts, so the lever wasn't fully tested against this cluster.

## What was tested
- Curated a SMALL web-verified current-VN-2025 corpus (general facts, NOT a qid→answer map):
  2-tier model, 34 provinces, Gia Lai merger=135 communes, etc. (`data/rag/current_vn_2025.jsonl`).
- Ran the harness BM25 retriever + the `has_legal_admin_strong` gate over the real BTC 463.

## Results
1. **Retrieval WORKS** — for the admin-reorg cluster the correct fact is surfaced #1 with a dominant
   score: test_0087 (2-tier) 13.51, test_0224 (135 communes) 5.42, test_0301 (Bình Định merge) 7.71.
   So the knowledge becomes retrievable once it's in the corpus. (Commune-level e.g. test_0254 needs
   a bigger corpus — not included.)
2. **But GATING FAILS both cheap ways:**
   - **Keyword gate** (`has_legal_admin_strong`, ≥2 of can-cuoc/thu-tuc/ho-so/cap-xa…): fires on 27/463
     (5.8%) but **misses** the reorg cluster (test_0087/0224/0301 share too few markers). Loosening to
     ≥1 "sáp nhập" over-fires on reading passages that mention mergers (test_0350/0363).
   - **Retrieval-score threshold**: 450/463 get some match; raw BM25 scores don't separate — the
     top-scored are RANDOM questions sharing common words (tỉnh/xã/2025). Threshold 5.0 fires 156
     (34%) → would inject the corpus into a third of the test = the measured "always-on RAG HURTS".
3. **Conclusion:** retrieval is not the blocker; **precise GATING is** — and no CPU/no-model gate
   cleanly selects the ~1-3% beneficiary slice. This reproduces, at the dev level, the prior verdict
   that targeted RAG nets flat/negative on the full mixed test. **No GPU A/B warranted for RAG.**

## The remaining (simpler) candidate — gate-free prompt context
The errors are dominated by a FEW high-frequency current facts (2-tier model, 34-province count).
A gate-free option: append a SHORT, accurate, general **"current-VN-2025 context"** line to the
reasoning system prompt for ALL questions (e.g. "Bối cảnh 2025: VN có 34 tỉnh/thành; chính quyền 2
cấp tỉnh+xã, bỏ cấp huyện từ 1/7/2025"). No retrieval, no gate.
- Upside: fixes the highest-frequency current-fact errors; generalizes to private.
- Risk: an always-on context line could distract/bias the other ~457 questions (every prior
  always-on lever — k>1, quant, router — hurt unexpectedly). **Cannot be dev-validated offline; needs
  ONE paired GPU A/B** (candidate vs 88.34 baseline, no-regression gate on the 431 agreed answers).
- Keep it SHORT + neutral-factual; if the A/B regresses non-admin questions, drop it.

## State
- 88.34 portable image stays the LOCKED submission.
- RAG-gate path: dev-disproven (this note). Do not spend GPU on it.
- Open candidate: gate-free current-VN-2025 prompt context — pending owner decision on one GPU A/B.
- Dev artifact `data/rag/current_vn_2025.jsonl` kept local (not committed; RAG path shelved).
