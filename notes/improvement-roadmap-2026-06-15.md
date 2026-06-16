# Neko Core improvement roadmap — the 88.77 → ceiling gap, analyzed by technique (2026-06-15)

Owner asked: tentatively accept 88.77, analyze the 88.77→93.74 gap, and research which
technologies/techniques/pipelines should improve Neko Core **stably and professionally**.
This note is data-grounded (the real 463 gap) + SOTA-grounded, and honest about the offline ceiling.

## 0. Frame (do not lose this)
- **93.74 is NOT a target.** It is codex = GPT-5.5 + web, with per-question public-463 answer flips —
  a FORBIDDEN model+web upper bound that an offline Gemma container cannot reproduce and that does not
  transfer to the 2000 private set. It is useful ONLY as a diagnostic oracle to size the gap.
- **The real target is the 2000 multilingual private set.** Every lever must generalize there; nothing
  tuned to the 463. (memory `feedback-rag-architecture-not-463-overfit`.)
- Constraints: offline, Gemma-4-26B-A4B-Q4 (+ Qwen3.5≤9B allowed), Time score matters.

## 1. Gap decomposition (32 disagreements 88.34-vs-codex, by ADDRESSABLE technique)
| Cluster | # | Addressable offline? | Lever |
|---|---|---|---|
| KNOWLEDGE trivia (chùa, RAID, kinh tế, địa lý…) | ~15 | ❌ mostly NOT | parametric gaps; only cross-model complementary knowledge, low-yield |
| QUANT / numeric reasoning (3-phase power, counts) | ~7 (≈3-4 true) | 🟡 partial | precise TIR + self-verification (logic/math) |
| READING (passage GIVEN, model still wrong) | 3 | ✅ YES | reading-grounding + verify-each-option-vs-passage |
| CIVICS / IDEOLOGY (Augustine, Morton Keller…) | 3 | 🟡 half knowledge | hard, low-yield |
| LAW-fact + RAG current-fact | 4 | ✅ partial | clean reform RAG (+2 PROVEN); law corpus DISPROVEN (−2) |

**Headroom is REASONING-shaped, not knowledge-shaped:** the only cleanly-addressable clusters are
READING (3), precise QUANT (~3-4), and the proven RAG (+2). The ~15-18 knowledge-trivia questions are
the hard offline ceiling — a corpus can't fix "the model doesn't know who the first abbot was," and a
general corpus HURTS (proven). So realistic offline headroom over 88.77 is **~+3-6 on the 463**, and
likely less on the multilingual private set.

## 2. Technique matrix (SOTA-grounded; what's NEW vs already-dead in Neko Core)
| Technique | SOTA basis | Cluster | Neko Core status | Verdict |
|---|---|---|---|---|
| **Reading-grounding** (quote→vet each option vs passage) | evidence-grounded QA; CoVe-on-passage | READING | **MEASURED DEAD** (battery existed): 90.00% vs self-consistency 91.67% on ViMMRC n=120 (−1.67pp, wash-to-negative) | **DEAD** — does not help; the built reading mode is wash/negative on the real model |
| **Chain-of-Verification / SETS** (draft→verify-questions→refine) | Dhuliawala'23, SETS Chen'25 (power-law past sampling plateau) | QUANT/logic | not built | **PROMISING** for logic/math; over-trust limits self-verify → use cross-family |
| **Cross-model verify (Qwen verifies Gemma)** | CoVe "cross-family > self"; MoA | QUANT, some knowledge | DEFERRED (Qwen adjudicator) | **MEDIUM** — precise verifier (not decider) on low-agreement; risky |
| **Precise TIR** (narrow numeric only, well-gated) | PAL/PoT | QUANT numeric | broad TIR MEASURED DEAD (−9.29pp; false-flipped 47) | retry ONLY with a high-precision gate |
| **Targeted RAG, clean small corpus** | this work | current-fact | **+2 PROVEN**; big corpus −2 | **SHIP** the 37-chunk reform corpus; do NOT grow it |
| Mixture-of-Agents (broad) | MoA; **but Self-MoA/"Rethinking MoA" 2025: mixing weaker models often doesn't help** | all | Qwen-standalone worse | LOW — broad mixing unlikely to beat self-consistency |
| maj@k / k>1 voting | — | all | MEASURED DEAD (wash; systematic errors) | dead |
| quant Q6/Q8, dense 31B | — | knowledge | MEASURED DEAD (worse / Time) | dead |

**Key SOTA caveat that explains Neko Core's dead levers:** self-verification and maj@k FAIL on
knowledge because the model OVER-TRUSTS its own systematic errors (logic/math benefit, knowledge does
not). This is WHY maj@k washed and why the knowledge cluster is hard. It also says the verification
levers should target the LOGIC/MATH/READING clusters and use CROSS-family (Qwen) signal, not self.

## 3. The PROFESSIONAL pipeline (the "ổn định + chuyên nghiệp" core — this matters more than any one trick)
The durable asset is not a technique; it is a disciplined improvement loop. This is exactly the loop
used today (RAG: measure→A/B→no-regression→honest negative on the law corpus). Codify it:

1. **Standing error-analysis harness** — every eval run auto-categorizes errors by cluster
   (reading / quant / knowledge / current-fact / defective-gold) and tracks per-cluster accuracy over
   time. You optimize what you measure. (Build: a small `analyze_errors.py` over pred + an oracle.)
2. **One lever = one focused module + config flag, default OFF** (AGENTS.md). Never touch unrelated
   layers; default path stays byte-identical.
3. **Labeled dev set per cluster** — small seeded sets (reading=ViMMRC, quant=ViGEText-math) so a
   lever can be measured WITHOUT burning the public-test budget or overfitting to it.
4. **Measured A/B + no-regression gate** — promote a lever ONLY if it wins its target cluster AND does
   not regress the agreed-correct answers. Real GPU numbers, never proxy/vibes. (Today's standard.)
5. **Adversarial / honesty check** — assume a lever HURTS until proven; report negatives loudly
   (the law-corpus −2 is a feature of the process, not a failure).
6. **Reproducibility** — pin the build (the ~1% non-determinism seen across llama-cpp builds means
   "baseline" must be re-measured in the same environment as the candidate, not vs a stale pred).

## 4. Prioritized next steps (UPDATED after measuring reading-grounding)
- ~~Reading-grounding~~ — **MEASURED DEAD** (90.00% vs 91.67% baseline on ViMMRC, battery already ran).
  The reading cluster is NOT improvable by the built grounding mode. Removed.
1. **Ship the proven clean RAG (+2)** behind the config gate (reranker, 37-chunk reform corpus) after
   one confirming 463 A/B. Bounded but the ONLY proven positive lever.
2. ~~Cross-model verification (Qwen3.5 verifies Gemma on low-agreement quant/logic)~~ — **MEASURED DEAD
   2026-06-16** (`notes/qwen-verifier-design-2026-06-16.md`). The challenger needs the diversified
   `tiered` base for a low-agreement signal (k=1 is deterministic, never fires); but `tiered` k=5 scores
   **82.67% on the 150-q quant dev set, −4pp BELOW the k=1 ship (86.67%)** — so cross-model is
   net-negative vs the ship regardless of Qwen. Re-confirms "diversified voting hurts quant; model
   over-trusts systematic errors." Built + tested (254 green) + kept as an Idea-writeup artifact, NOT shipped.
3. **Accept the ceiling.** Reading-grounding dead, maj@k dead, broad TIR dead, quant-swap dead, 31b
   forfeits Time, big corpus harmful. The knowledge-trivia cluster (~15) is unfixable offline. The
   honest offline ceiling is ~88.77 (RAG +2) + at most a couple of quant questions if a precise
   cross-model verify lands — call it **~89-90 on the 463, likely less on the private 2000.**
- **Most important professional output:** the LOOP in §3 + checking EXISTING measured results before
  spending GPU (reading-grounding was already measured — don't re-run what's known).

## 4b. COMPLETE measured battery (labeled dev sets, n=120, real 26B Gemma) — decisive
| Cluster | self-consistency (default) | best alt workflow | 31b (Time-rejected) |
|---|---|---|---|
| READING (ViMMRC) | **91.67%** | reading-ground 90.00% ✗ | 94.17% |
| QUANT (ViGEText) | **86.67%** | router/TIR 79.17% ✗✗ | 89.17% |
| CIVICS (ViGEText) | **91.67%** | forced-RAG 86.67% ✗ | 92.50% |

**Decisive: default self-consistency BEATS every alternative workflow on every cluster.** TIR/reading-
grounding/forced-RAG/k5-vote are all wash-or-worse. Only the bigger 31b model wins (+2-3pp) and it
forfeits the Time score (~90s/q vs 2.9s/q). So the only feasible improvement over self-consistency is
the **GATED targeted RAG (+2)** — it helps precisely because it fires on ~4 questions, NOT on all
(forced-RAG-on-everything LOSES 5pp on civics, as the battery shows). This is why "more RAG" hurts and
"narrow gated RAG" helps.

## 4c. Cloze / logprob extraction — letter-logprob MEASURED DEAD (2026-06-15)
Tested the orthogonal "gut-probability" signal (no-CoT) the workflow battery never ran. Letter-logprob
(read next-token logprob of each option letter) on the 3 labeled dev sets (Gemma 26B, GPU):
| Set | self-consistency | cloze-letter | note |
|---|---|---|---|
| QUANT | 86.7% | **27.5%** | heavy A-bias (86/120 → A) |
| CIVICS | 91.7% | **30.0%** | A-bias (91→A) |
| READING | 91.7% | **50.8%** | A/D-bias |

On SC-WRONG questions cloze recovered only 8 total (mostly A-bias coincidence) while it would BREAK
202 SC-right answers → ensemble is net-catastrophic. **Letter-logprob cloze is DEAD** (it reads a
positional/letter prior, not the model's real belief). CAVEAT: this is the WEAK method; the fair
option-likelihood (content-scoring, bias-free) was dropped for cost and is UNTESTED — but the
systematic-error nature predicts it also correlates with SC errors (low probability). A portable
GGML_NATIVE=off llama-cpp wheel was captured (`pod_ab/out/llama_cpp_portable.tar.gz`, 211MB) so any
re-run skips the ~25-min build.

## 5. Honest ceiling statement
- **Offline Gemma ceiling ≈ 88.77 + a few reasoning-cluster questions (maybe ~90 on the 463), bounded
  by the knowledge cluster.** Not 93.74 (forbidden model+web).
- The professional win is the LOOP + the harness (reusable, measured, honest), not a single score jump.

## Sources
- Chain-of-Verification: Dhuliawala et al. (learnprompting.org/docs/advanced/self_criticism/chain_of_verification);
  SETS Chen et al. 2025; "self-verify over-trusts; cross-family > self; knowledge gains marginal".
- Mixture-of-Agents (ICLR 2025) + Self-MoA / "Rethinking MoA: is mixing different LLMs beneficial?" 2025.
- Neko Core measured results: `notes/rag-dense-gate-2026-06-15.md`, RESUME-HERE dead-lever list.
