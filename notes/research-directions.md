# Research directions (deferred — pursue only after CoT is proven better)

Date opened: 2026-06-10. Gating principle: **first confirm CoT > baseline on the real model
(full 463 + leaderboard). If CoT is not better, none of these matter.**

## 1. Tiering (speed) — DEFERRED
CoT costs ~5s/q (vs ~0.8s/q letter-only) → ~2.9h for 2000q. If accuracy wins, cut average
time by routing: **letter-only for easy/factual short items, full CoT only for hard
(calculation / multi-step / reading)**. Lever for the 10-pt time score *without* losing the
accuracy of CoT. Only worth building once CoT's accuracy edge is confirmed.

## 2. Concise-reasoning prompt (speed) — DEFERRED
Reasoning tokens are *where accuracy comes from* (can't be removed), but the *length* is
tunable: prompt for "reason in 2–3 short steps, then ANSWER:". Reduces avg tokens/time while
keeping the benefit. There is a floor (calculation needs the steps). Tune against accuracy.

## 3. Web search / retrieval — partially CORRECTED (see update below)
The contest container is **offline & self-contained** (reads /data, writes /output/pred.csv,
no network). **Web search is impossible in the runtime** — this part is permanent and correct;
knowledge gaps from *live* web data cannot be answered.

> **CORRECTION (2026-06-15):** the original claim "no corpus to retrieve from → rerank/embedding
> add nothing" is OUTDATED. A packaged OFFLINE corpus *was* later built (`data/rag/legal_corpus.jsonl`
> from VN statutes + `scripts/build_rag_corpus.py`), and a BM25 retriever + `rag` workflow + router
> ship in the code. Offline RAG over a baked corpus is therefore *possible* (no network needed).
> The real verdict is more nuanced: **retrieval WORKS but GATING fails** — no cheap (CPU-only) gate
> cleanly selects the ~1-3% legal/admin slice that benefits, so always-on/loosely-gated RAG injects
> noise and nets flat/negative. Measured-dead as a *gated* lever, NOT because "no corpus exists."
> Full evidence: `notes/rag-oracle-dev-2026-06-15.md`, `notes/router-tir-measured-2026-06-13.md`,
> `notes/2026-06-13-guardrail-fix-and-accuracy-research-frame.md` (§Phase 4). BGE-m3/Qwen-Rerank are
> allowed by the rules but unused (BM25 was sufficient for the dev test); do not add them without a
> measured win.

## 4. Sensitive / culturally-specific robustness — TEST PLANNED
Vietnamese-authored civics/history/geography MCQ expect the **Vietnamese-official answer**
(e.g., Hoàng Sa & Trường Sa are Vietnamese sovereign territory). Gemma (Google, global
training) may: give a "disputed" framing, align differently, or refuse — any of which yields
the *wrong* MCQ answer. **Risk for the VN private set.** Plan: probe the real model with a
sovereignty MCQ (both baseline and CoT) and observe. If it answers wrong/refuses:
- mitigation A: a system-prompt that sets the answering frame to the Vietnamese curriculum /
  official context (general, not per-question — avoids overfit);
- mitigation B: a narrow override only for a tightly-matched class (use sparingly — this is
  the overfit pattern we otherwise avoid);
- mitigation C: accept the loss if such items are rare.
Decide based on how the model actually behaves.

## 5. Real self-consistency (temp>0) + cross-model challenger — DEFERRED
k=5 at temp=0 is wasteful (identical samples). For genuine agreement-calibration: sample at
temperature>0 so reasoning paths diverge → vote + a real confidence signal → drive tiering
and the cross-model (Qwen3.5-8B) challenger on low-agreement items. Only valuable if the
extra compute recovers accuracy beyond single CoT. Measure before adopting.

## 6. Error analysis on the full 463 — NEXT after the run
From run-base-full vs run-cot-full: the answer-diff set (where they disagree) is the place to
study *which* question classes CoT helps vs hurts. Drives prompt + tiering decisions.
