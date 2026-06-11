# Public test (463) REAL composition — ground truth, 2026-06-11

Analyzed the actual 463-question public test (`public-test_1780368312.json`), not a proxy.
This corrects a key earlier error: **ViGEText is a BAD proxy** — it is bare 4-choice STEM
exam questions with no passages, whereas the contest is passage-heavy reading comprehension
+ cross-domain quantitative + a factual grab-bag, with many 10-choice items.
Owner confirmed independently: "khá nhiều là logic" and "toán học … tổng quát trên tất cả
các lĩnh vực … Hóa Lý, Lượng Tử".

## Composition (structural classifier, passage-priority)

| Category | Count | % | Lever | RAG? |
|---|---|---|---|---|
| factual / other | 252 | 54.4% | CoT+SC; legal/admin subset → RAG | partial |
| reading comprehension (passage given) | 100 | 21.6% | careful grounding + SC | **no** (text supplied) |
| quantitative (calc) | 90 | 19.4%* | **TIR (Python exec)** + SC | no |
| logic | 21 | 4.5% | reasoning + SC | no |

\* UNDERCOUNT — the classifier misses LaTeX-only quantitative (e.g. test_0031 number
theory `x≡2 mod 5`, test_0042 production function `Q=2K^0.5L^0.5`) that landed in
"factual". True quantitative is ~25-30%. TIR's target is bigger than 19%.

## Structural facts (decision-grade)

- **29% are 10-CHOICE questions (134/463).** Random baseline 10%, not 25%. The 10-choice
  set skews quantitative+logic (68/134). Position bias matters more here → keep the cyclic
  choice-permutation debiasing; spend more SC samples / escalate on these.
- Choice-count distribution: 4-ch=318, 10-ch=134, plus a few 2/3/5/11.
- **Context is SAFE**: max input ≈ 3399 tokens (p99 ≈ 2897). n_ctx=8192 never truncates;
  no long-passage data loss. (The scary 8712-CHAR max is only ~3.2k tokens.)
- Negation in the asked part ≈ 3.5% (lower than the ViGEText analysis implied once
  restricted to the question, not the passage) — a minor, not major, lever.

## The factual bucket (211, the RAG question)

A grab-bag: (a) Vietnamese law/administrative/Party-HCM ideology — fire-safety approval
(test_0010), Cà Mau ID-card procedure (0022), legal-entity suspension (0019), Hồ Chí Minh
Thought (0041) → **the ONE real RAG target** (legal corpus + vi-wiki); (b) niche local
facts (first transmitter at An Phú pagoda 0030) → RAG only if corpus happens to contain it;
(c) general knowledge/etiquette → model already knows; (d) misclassified quantitative → TIR.
RAG's realistic reachable slice ≈ 10-15% of the test, and only the *retrievable-verbatim*
part of that — narrow and uncertain, but non-zero (unlike the reading-comp bucket where
RAG is strictly useless because the text is already in the prompt).

## "Good combination" architecture (owner's ask: phải có sự kết hợp tốt)

A question-type ROUTER on top of CoT + self-consistency + position-debiasing (all built):
1. **Passage detected → reading-comp mode**: CoT that grounds each option in the supplied
   text, rejects plausible-but-unsupported distractors (test_0001's trap: a crime that IS
   stoning-punishable but in the WRONG source). RAG OFF. ~22%.
2. **Quantitative detected → TIR mode**: emit + EXECUTE Python (offline sandbox), SC on the
   SETUP not just the arithmetic (avoid "solves the wrong system"). ~25-30%, heavy in
   10-choice. This is the owner's "toán tổng quát mọi lĩnh vực" (econ/calc/kinetics/stats).
3. **Legal/admin/Party/civics factual → optional RAG mode**: vi legal corpus + wiki, CoT.
   ~10-15%, uncertain — build LAST, gated, measure before trusting.
4. **Else → standard CoT + SC.**
5. **10-choice → more SC samples + cyclic permutation debias (built).**

## Build priority (revised on ground truth)
1. **TIR for the quantitative slice** — highest-confidence, largest single addressable
   bucket (~25-30%), matches owner's emphasis, generalizes (universal math). Build first.
2. **Reading-comp grounding mode** — second biggest bucket (~22%), reasoning-only, no new
   infra (a prompt/strategy variant + SC).
3. **Targeted RAG** for the legal/admin/Party factual slice — last, gated, measure first.
4. Position-debias + SC-on-10-choice — already built; just ensure it fires on 10-choice.

## Dev-set implication
ViGEText (bare STEM) only proxies the quantitative slice. For honest measurement we also
need a READING-COMPREHENSION labeled proxy (ViMMRC, Vietnamese MRC) and ideally a
legal-MCQ proxy. Measure each lever on its matching proxy, not on one ill-fitting set.
