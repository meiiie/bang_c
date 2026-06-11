# Error-lever analysis — RAG vs TIR vs reasoning (2026-06-11)

Source: 33-agent adversarial workflow (`wf_632b6530-25a`) over the 16 misses of the
control variant (old Q4_0, k=1 CoT) on the 150-question ViGEText dev set. Each error
categorized + each fixability verdict independently refuted, several with executed Python.
Full transcript: tasks/wm5qt8jcq.output. Battery numbers: see worklog 2026-06-11.

## Verified tally (n=16)

| Lever | yes (clean win) | partial (conditional) | no (useless) |
|---|---|---|---|
| Offline-RAG | **0** | 7 | 9 |
| TIR (Python exec) | **2** | 4 | 10 |

## The three findings

### 1. ~6/16 "errors" are DATASET DEFECTS, not model errors
- **biology genetics (gold C=20%)**: 20% = 1/5 is mathematically UNREACHABLE from a
  one-gene/two-allele Punnett; the model's 25% is genetically CORRECT. Gold is defective.
- **math 2^(x+1)<4 (gold D)**: option D literally written `(-∞;1)]` (mismatched bracket);
  option corruption, not a reasoning failure.
- **chemistry thermite / FeE / X-axit, physics uRL**: truncated stems — PARTLY an artifact
  of *our* transcription shortening the questions with "…" for the workflow; the real
  harness sees full stems. So these specific "underdetermined" verdicts are not proof of
  real harness failures.
- Implication: the model's TRUE accuracy on clean items is HIGHER than the measured
  89.33%. Do NOT tune against these — quarantine defective/suspect golds.

### 2. RAG has zero clean wins; every RAG-"partial" is gated on a reasoning step
The discriminating *fact* is often lookuppable (lysine is diamino; 1972 didn't end the
war; Na2CO3 softens hardness) but the deciding *step* is multi-way comparison / negation
parsing / option-matching that retrieval cannot close. For the Vietnamese-exam
"ý nghĩa / điểm giống nhau / câu nào KHÔNG đúng" genre, RAG caps at partial.

### 3. TIR wins only on fully-specified numeric items, and only after correct setup
2 clean wins (combustion V=8.96L, lysine 55.60g) — explicit O2/mass-balance code kills the
exact arithmetic slip. But TIR faithfully solves the WRONG system if the model mis-models
the problem (chem-X-axit, FeE, physics-uRL are "partial" for this reason). TIR amplifies a
correct setup; it does not create one. On EVERY humanities item TIR = no (zero compute).

## Strategic conclusion (verified memo)

This dev set is STEM-skewed; the contest (2000q) is broader (civics/law/history/
literature/economics + STEM). As the mix shifts to humanities:
- TIR's value collapses toward 0 (useless on every humanities item here).
- RAG's ceiling stays at "partial" (humanities failure = discrimination, not missing fact).
- The only lever that helps the broad distribution AND unblocks TIR's conditional STEM
  wins is **reasoning robustness: CoT + self-consistency (HAVE) + negation/quantifier-
  aware parsing (NEW, cheap, generalizing)**.

## Build order (do NOT reorder without new evidence)

1. **Contest-representative dev set + error-composition triage** — measure % numeric-
   computable vs % reasoning-discrimination vs % dataset-defect on a humanities-weighted
   slice. De-risks everything. (In progress: run-HUM.)
2. **Reasoning robustness** — keep CoT+SC; ADD explicit negation/quantifier handling for
   "KHÔNG / không phải / luôn / chỉ / đều" stems (≥2 errors here were this; pervasive in VI
   humanities MCQ; zero overfit risk — universal MCQ skill).
3. **Gated TIR** — Python execution for the numeric slice ONLY, behind a "is this
   deterministic-numeric?" classifier; self-consistency on the SETUP, not just arithmetic,
   to avoid the "solves the wrong system" trap. Real (2 confirmed wins) but narrow.
4. **Offline-RAG (LOWEST)** — 0 clean wins, capped at partial; build only if the broad-set
   triage proves a real "missing-fact" bucket (specific statutes/dates/accords) retrieval
   can supply verbatim.

## Rejected this session (measured, not guessed)
- Quant swap to UD-Q4_K_XL: old Q4_0 scored ABOVE it (89.33 vs 88.00). REJECT.
- Blanket few-shot: flat (+1 Q, noise). Keep OFF by default.
- Blanket tiered: +0.67pp at 3× the time. Optional disagreement-only escalation at most.
