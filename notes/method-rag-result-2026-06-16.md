# Method-RAG (RAG-for-reasoning) — MEASURED +2 on quant (2026-06-16)

Owner's hypothesis (correct): even for "reasoning" questions, if the gap is "doesn't know the
formula/method", giving the model a reference (like a human consulting a formula sheet) helps. I had
wrongly called reasoning "no-corpus". Tested it; the owner was right.

## Setup
- Method corpus: `data/rag/method-vault/` → `method_corpus.jsonl`, 17 atomic method chunks (12 math, 3
  chemistry, 2 physics) — general SGK-THPT formulas/procedures, NOT question-specific.
- Reused the PROVEN dense-gate RAG: `rag-gated` workflow, `rag_corpus_path = method_corpus`, reranker
  gate (threshold 0.4 for this test), inject the relevant method as a fallible reference.
- 2 arms, in-process k=1 (ship config), over the 150-q labeled quant dev set, scored vs `quant.gold.csv`.
  Pod RTX 3090, ~$0.42. (Wheel build was pathologically slow on the host, ~72 min — host CPU, not a bug.)

## Result — POSITIVE
| Arm | quant accuracy |
|---|---|
| A: self-consistency (no method-RAG) | 121/150 = **80.67%** |
| B: **method-RAG** | 123/150 = **82.00%** |
| **net** | **+2** |

Gate fired on 33/150 (~22% @ thr 0.4). Changed 4 → **fix=3, false-flip=1**:
- 2023_chemistry_75: C→**D** (gold D) FIX
- 2019_chemistry_64: A→**D** (gold D) FIX
- 2023_physics_37: B→**D** (gold D) FIX
- 2017_physics_35: A→B (gold A) **FLIP** (method misled where SC was right)

## Reading (validates the theory)
- The fixes are **CHEMISTRY + PHYSICS** (method-knowledge: ester naming, fiber types, mol; pendulum /
  thermal-expansion formulas). **NO math (calculus) changed** — the 26B already knows derivatives/logs;
  there the gap is execution, not formula-recall. So method-RAG helps EXACTLY the "doesn't-know-the-method"
  slice (chem/physics), as RAG-for-reasoning research predicts. The owner's intuition was right.
- **This is the SECOND proven positive lever** (after current-fact RAG +3). Both reuse the same dense gate.

## Honest caveats
- Small absolute gain (+2/150 = +1.33pp on the probe); bounded.
- 1 false-flip → the gate over-fires a bit at thr 0.4 (33 fires). Tune the threshold up via a gate-audit
  to cut over-firing / the flip (may lose a fix — measure).
- **Time cost:** Arm B wall 1218s vs Arm A 943s = **+29%** (reranker per question on CPU). On the 2000
  private this is a real Time-score hit — weigh it; reranker on GPU or a cheaper pre-filter would help.
- Generalization: +2 is on the dev probe; the 2000-private (multilingual, more science) is the real test.

## Next (if pursued)
1. Tune the method-gate threshold (gate-audit) to keep the fixes, drop the false-flip / over-fires.
2. Expand the chem/physics method corpus (where it helps); keep math light (no help there).
3. Integrate into the ship: a COMBINED corpus (current-fact + method) OR a dual gate, so `rag-gated`
   handles both the current-fact slice (+3) and the quant-method slice (+2). Measure the combined run +
   the Time cost before shipping. The locked 88.34 + rag-gated 88.98 stay the safe fallbacks.
