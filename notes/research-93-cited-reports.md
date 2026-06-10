# Cited research reports — push 87.26 to 93+ (2026-06-11)

Produced by a 3-agent web-research workflow. Each section is a standalone cited report.



---

# REPORT: diversity-voting

# Diversity + Voting for Single-Model MCQ Accuracy — Research Report

Target: Gemma‑4 26B‑A4B (MoE, QAT Q4_0, llama-cpp-python, GPU, offline), 2000 mixed Vietnamese/multilingual MCQs (4–10 choices), baseline 87.26 with single greedy CoT + "ANSWER: X".

---

## (a) Self-consistency (Wang et al. 2022, arXiv:2203.11171)

**Mechanism & headline numbers.** Sample k CoT paths at temp>0, majority-vote the final answer. Original paper ([Wang et al., ICLR 2023](https://arxiv.org/abs/2203.11171), [full text](https://ar5iv.labs.arxiv.org/html/2203.11171)):
- Sampling settings used: **UL2-20B / LaMDA-137B: T=0.5, top_k=40; PaLM-540B: T=0.7, top_k=40; GPT-3: T=0.7, no top-k**. Paper states SC is "robust to sampling strategies and parameters" across T=0.5–1.0.
- **Diminishing returns curve** (GSM8K, PaLM-540B): greedy 56.5% → ~68% @ k=5 → ~71% @ k=10 → 74.4% @ k=40. **~70–80% of the total gain arrives by k=5–10**; k>15 is poor ROI. Practitioner consensus is the same: best cost/benefit at 5–10 paths ([survey](https://arxiv.org/html/2502.19830v1), [practitioner guide](https://www.promptedit.app/prompt-framework/self-consistency)).
- **Math ≫ knowledge gains**: GSM8K **+17.9pp**, AQuA **+12.5pp**, SVAMP **+7.6pp** vs StrategyQA **+6.3pp**, ARC-challenge **+3.5pp**, **CommonsenseQA only +1.7pp**. Expect your knowledge-heavy Vietnamese MCQs to gain **~+1.5–4pp** from SC alone; math/logic subsets gain more.

**Optimal temperature for voting.** [Du et al. 2025, "Optimizing Temperature for Language Models with Multi-Sample Inference"](https://arxiv.org/html/2502.05234v2): optimal T for majority voting is **higher than for single-sample** ("at smaller sample sizes, lower temperatures tend to produce better accuracy; higher temperatures yield better results as sample size increases"); general instruction-tuned models optimal at **T≈0.5–0.7**, task-specialized at 0.9–1.1; optimum stabilizes past k=32. The [dynamic-alignment analysis](https://arxiv.org/pdf/2502.19830) confirms: single-sample accuracy falls with T but converged-SC accuracy rises, optimum often near T=1.0. **Gemma-specific override:** Google/Unsloth ship Gemma with **T=1.0, top_k=64, top_p=0.95, min_p=0** as the tuned operating point ([Unsloth Gemma guide](https://unsloth.ai/docs/models/tutorials/gemma-3-how-to-run-and-fine-tune), [Gemma-4 QAT docs](https://unsloth.ai/docs/models/gemma-4/qat)), and users report **lowering T below 1.0 degrades Gemma‑4 quality** monotonically (tested 0.8/0.6/0.3) ([HF discussion on your exact model](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/21)). → Use **T=1.0 with Gemma's native sampler chain** for diversity paths; keep one greedy path as anchor.

**Cost control.** [Early-Stopping Self-Consistency (ESC, arXiv:2401.10480)](https://arxiv.org/html/2401.10480v1): sample in windows (e.g., 3), stop when a window is unanimous — **cuts samples up to ~80%** (GSM8K, StrategyQA) with no measurable accuracy loss. [Adaptive-Consistency (Aggarwal et al., EMNLP 2023)](https://www.researchgate.net/publication/376401874_Let's_Sample_Step_by_Step_Adaptive-Consistency_for_Efficient_Reasoning_and_Coding_with_LLMs) similar (3–4× fewer samples, <0.1pp drop) but needs a tuned threshold. ESC is the right fit for your 10-pt time budget.

## (b) Position/order bias — the bigger lever for knowledge MCQ

**Magnitude.** [Zheng et al., ICLR 2024 "LLMs Are Not Robust Multiple Choice Selectors"](https://arxiv.org/abs/2309.03882) ([full text](https://ar5iv.labs.arxiv.org/html/2309.03882)): 20 LLMs show systematic **selection bias** (prior mass on specific option-ID tokens), RStd up to 8–11pp on MMLU/CSQA for mid-size models. [Pezeshkpour & Hruschka 2023](https://arxiv.org/pdf/2308.11483) ([blog](https://megagon.ai/order-matters-llm-sensitiv-mult-choice-tsks/)): reordering options swings performance by **up to 75% relative** for GPT-4-class models in adversarial order; best-vs-worst ordering gap up to 50–70pp ([permutation attack paper](https://arxiv.org/pdf/2310.01651)). A ~26B model at Q4 will have non-trivial bias — this is likely a meaningful chunk of your remaining 13pp error.

**Effect sizes of debiasing (Zheng et al., 0-shot MMLU avg):**

| Method | Extra compute | Accuracy gain |
|---|---|---|
| Full permutation averaging | ×n! (infeasible) | **+4.9pp** |
| **Cyclic permutation** (each content seen at each position once) | ×n (×4 for 4 options) | **+1.2pp** |
| PriDe (prior from 5% of set) | ×1.15 | **+2.6pp** |
| PriDe (40%) | ×2.2 | +4.1pp |

Crucially, Zheng et al. show debiasing flips **more wrong→right than right→wrong**, i.e., real accuracy gains, not just consistency. Majority voting over option permutations independently reported worth **up to +8pp** ([Pezeshkpour & Hruschka](https://arxiv.org/pdf/2308.11483); see also [BaQCKV efficient permutation voting](https://arxiv.org/html/2511.21709), [SCOPE](https://arxiv.org/pdf/2507.18182)).

**Practical schemes, best-first for your setup:**
1. **Cyclic rotation + majority vote** (rotate contents by 1 position per pass, remap letters back, vote on *content*): linear cost, no labels needed, language-agnostic. For 4–5 choices use all n rotations; for 6–10 choices use a **random sample of 3–5 rotations** (full cycle unnecessary; gains saturate).
2. **PriDe** is cheapest but assumes direct option-ID probability prediction (first-token logprobs), not CoT→"ANSWER: X". With CoT, permutation voting is the compatible scheme. Caveat: [Wang et al. 2024 "Look at the Text"](https://arxiv.org/html/2404.08382v1) shows instruction-tuned models' **text answers are far more robust than first-token probabilities** (when mismatch >50%, plain text answers beat even PriDe). Your CoT+extracted-answer pipeline is already on the robust side — keep it; don't switch to logprob-only scoring.

## (c) Prompt-format diversity vs sampling diversity

- [Wang et al. 2022, "Rationale-Augmented Ensembles" (arXiv:2207.00747)](https://arxiv.org/abs/2207.00747): comparing prompt-order/input-space perturbation vs output-space sampling, **"rationale sampling in the output space is the key component to robustly improve performance"** — sampling diversity > prompt-phrasing diversity as a single axis.
- [Naik et al. 2023, DIV-SE (arXiv:2310.07088)](https://arxiv.org/abs/2310.07088): LLM-generated *approach/persona-diverse* prompts ensembled at greedy decoding beat temperature-only SC at fixed budget (up to +29.6pp on planning tasks; +9.9pp GPT-4 AQuA) — but gains were demonstrated mostly on planning/hard-math, with handcrafted approach generation; transfer to multilingual knowledge MCQ is unproven.
- **For MCQ specifically, the strongest "diversity" axis is choice-order permutation**, because it directly cancels the dominant structured error (selection bias) rather than just resampling reasoning noise. Ranking for your task: **permutation ≥ sampling > prompt re-phrasing**. Best practice: *compose* permutation with sampling (each vote uses a different rotation AND a different seed) — diversity compounds at zero extra cost per vote.

## (d) Seeded sampling reproducibility in llama.cpp / llama-cpp-python

- llama-cpp-python exposes `seed` in the `Llama` constructor and per-request (`create_completion(..., seed=...)`); the sampler RNG is seeded, so **given identical logits, sampling at T>0 is deterministic per seed** ([llama.cpp docs](https://gitlab.informatik.uni-halle.de/ambcj/llama.cpp/-/blob/889bdd76866ea31a7625ec2dcea63ff469f3e981/examples/main/README.md), [llama-cpp-python #972](https://github.com/abetlen/llama-cpp-python/issues/972)).
- **Caveat — logits themselves can drift on CUDA**: [llama.cpp #2838](https://github.com/ggml-org/llama.cpp/issues/2838) documents non-determinism with CUDA offload (GEMM kernel/tensor-core paths; floating-point non-associativity; results depend on batch composition). Same seed + same build + same GPU + **single-sequence decode (n_parallel=1), fixed n_batch/n_ubatch, no prompt-cache reuse across different prompts** is reproducible in practice; parallel slots or batch-size changes break bit-exactness ([reproducibility analysis](https://www.ingonyama.com/post/solving-reproducibility-challenges-in-deep-learning-and-llms-our-journey)).
- **Practical stance for the competition:** use `seed=f(question_id, vote_index)` so each vote is a *distinct, re-runnable* path. Treat seeds as diversity control + approximate reproducibility, not a cross-machine guarantee. For your one greedy anchor pass, force `top_k=1` rather than relying on `temperature=0` alone ([guidance](https://www.keywordsai.co/blog/llm_consistency_2025)).

## (e) MoE (26B‑A4B) + Q4 quantization sampling quality

- **Router fragility is the known MoE-specific risk**: quantization-induced logit perturbation can flip Top-K expert routing, and rarely-activated experts are under-calibrated ([MoE quantization theory, arXiv:2604.06515](https://arxiv.org/html/2604.06515v1); [APEX-quant](https://github.com/localai-org/apex-quant)). llama.cpp GGUF quants keep router/gate tensors at high precision, and **QAT Q4_0 specifically trains through the quantizer**, so Google's QAT checkpoints are near-bf16 quality ([Google QAT blog](https://blog.google/innovation-and-ai/technology/developers-tools/quantization-aware-training-gemma-4/), [VRAM/quality guide](https://chatforest.com/builders-log/gemma-4-qat-on-device-vram-reduction-builder-guide/)). **Keep the official QAT Q4_0; do not re-quantize** (community Q4_K_M non-QAT showed run-to-run reasoning inconsistency on this exact model: [HF discussion](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/21)).
- **Temperature interaction**: Gemma‑4 is tuned for T=1.0; lowering T *hurt* it in user tests (above). Two Q4-specific notes: (1) quantization slightly flattens/noises logits, so use **min_p=0.0 but keep top_k=64/top_p=0.95 to clip the noisy tail** at T=1.0; (2) **sampler order matters** — llama.cpp's default chain differs from Gemma's intended `temperature → top_p → top_k`; set the chain explicitly (`samplers` parameter) ([HF discussion](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/21), [Unsloth](https://unsloth.ai/docs/models/gemma-4)). At T=1.0 with voting, an occasional derailed path is harmlessly outvoted.

---

## Recommended recipe (concrete)

**Sampler config (all diversity passes):** `temperature=1.0, top_k=64, top_p=0.95, min_p=0.0`, sampler chain `temperature;top_p;top_k`, `seed = hash(qid)*31 + vote_idx`, n_parallel=1. **Anchor pass:** current prompt, original choice order, `top_k=1` (greedy).

**Per question (ESC-style two stage, vote on option CONTENT after de-permuting letters):**
1. **Stage 1 — 3 votes:** (i) greedy anchor, original order; (ii) T=1.0, choices rotated by 1; (iii) T=1.0, rotated by 2 (for n>5 choices, use 2 random rotations instead). If all 3 agree → answer. Expect unanimity on ~70–85% of questions (your baseline is 87%-accurate, so most are easy).
2. **Stage 2 — escalate to 7 total** on disagreement: add 4 more T=1.0 votes covering remaining rotations (and reversed order as one variant), distinct seeds. **Plurality vote; tie-break = greedy anchor's answer.**

**Expected effect (stacked, honest ranges):** SC@k≈7 on disagreed subset **+1.5–4pp** ([Wang et al.](https://arxiv.org/abs/2203.11171): CSQA +1.7 ↔ AQuA +12.5 depending on math share) + permutation debiasing **+1–3pp** ([Zheng et al.](https://arxiv.org/abs/2309.03882): cyclic +1.2, full-perm ceiling +4.9; [voting +up-to-8pp](https://arxiv.org/pdf/2308.11483)), partially overlapping → realistic **87.3 → 90–92.5**. Compute: ~3.2–3.8× current tokens with ESC (vs 7× naive), fitting the secondary time budget; cap escalation per-question (max_tokens) to bound tail latency.

**Pitfalls to avoid:** don't vote on raw letters (must remap through the permutation); don't lower T below ~0.9 for Gemma‑4; don't run multiple slots in one llama.cpp context if you want seed stability; don't replace CoT-text extraction with first-token logprobs ([Look at the Text](https://arxiv.org/html/2404.08382v1)).

Sources: [Wang et al. 2022 (self-consistency)](https://arxiv.org/abs/2203.11171) | [Du et al. 2025 (temperature for multi-sample)](https://arxiv.org/html/2502.05234v2) | [Zheng et al. 2023 (selection bias / PriDe)](https://arxiv.org/abs/2309.03882) | [Pezeshkpour & Hruschka 2023 (order sensitivity)](https://arxiv.org/pdf/2308.11483) | [Naik et al. 2023 (DIV-SE)](https://arxiv.org/abs/2310.07088) | [Wang et al. 2022 (rationale ensembles)](https://arxiv.org/abs/2207.00747) | [Wang et al. 2024 (Look at the Text)](https://arxiv.org/html/2404.08382v1) | [ESC](https://arxiv.org/html/2401.10480v1) | [Adaptive-Consistency](https://www.researchgate.net/publication/376401874_Let's_Sample_Step_by_Step_Adaptive-Consistency_for_Efficient_Reasoning_and_Coding_with_LLMs) | [llama.cpp #2838 (CUDA non-determinism)](https://github.com/ggml-org/llama.cpp/issues/2838) | [llama-cpp-python #972](https://github.com/abetlen/llama-cpp-python/issues/972) | [Google Gemma QAT](https://blog.google/innovation-and-ai/technology/developers-tools/quantization-aware-training-gemma-4/) | [Unsloth Gemma-4](https://unsloth.ai/docs/models/gemma-4) | [gemma-4-26B-A4B GGUF temperature discussion](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/21) | [MoE quantization](https://arxiv.org/html/2604.06515v1) | [APEX-quant](https://github.com/localai-org/apex-quant)


---

# REPORT: scoring-verification

# Answer-Scoring & Verification for Offline MCQ — Research Report

**Setup context:** Gemma-4 26B MoE (A4B) Q4_0 GGUF via llama-cpp-python, optional Qwen3.5≤9B; 2000 Vietnamese-heavy MCQs, 4–10 choices; baseline = single greedy CoT pass at 87.26 (letter-only direct = 77.11). Accuracy 80pts >> time 10pts.

**The single most important calibration point:** your own A/B (CoT 87.26 vs direct-letter 77.11) reproduces the [MMLU-Pro finding](https://arxiv.org/abs/2406.01574) that on 10-option, reasoning-heavy MCQ, CoT is *essential* while on classic MMLU it barely matters ([Sprague et al. 2024](https://arxiv.org/abs/2409.12183): ~95% of MMLU CoT gain is confined to questions containing "="). Conclusion up front: **logprob scoring must augment CoT, never replace it** on this dataset.

---

## Ranked by expected accuracy-per-inference-cost

| Rank | Technique | Expected Δ on your 87.26 | Extra cost (2000 Q) | Verdict |
|---|---|---|---|---|
| 1 | CoT → final-letter **logit readout** (replace regex extraction, harvest confidence) | +0.5 to +1.5 | ~0 (1 extra decode position) | DO FIRST |
| 2 | **Confidence-gated self-consistency** (resample only low-confidence Qs, majority vote) | +2 to +4 | ~1.3–1.8× wall-clock | DO |
| 3 | **Option-permutation vote / PriDe debias** on low-confidence subset | +0.5 to +1 | ~1.1–1.2× | DO (folds into #2) |
| 4 | **Cross-model escalation**: Qwen3.5-9B solves independently, vote/arbitrate on disagreements | +0.5 to +1.5 | small (9B is cheap, ~15% of Qs) | DO IF TIME |
| 5 | Hybrid logprob choice-scoring (PMI / length-normalized) as auxiliary ensemble signal | +0 to +1 | 1 short scoring pass per Q | OPTIONAL |
| 6 | Elimination prompting (global) | **−5 to −14** | — | AVOID |
| 7 | "Are you sure?" self-verification round | **−1 to −17** | — | AVOID |
| 8 | Pure cloze/logprob scoring replacing CoT | **≈ −10** (your own data) | — | AVOID |

---

## (a) Logprob / cloze choice scoring

**Core findings:**

- **Cloze scoring loses to letter-prompting (MCSB) for capable instruct models.** [Robinson & Wingate 2022](https://arxiv.org/abs/2210.12353) ([ar5iv](https://ar5iv.labs.arxiv.org/html/2210.12353)): multiple-choice prompting beat cloze prompting by **+8.3 (0-shot), +12.2 (1-shot), +9.7 (few-shot) points** averaged over 20 datasets with Codex, max +44.3 on CosmosQA, with **4.3× fewer forward passes**. MCSB has been validated specifically for **Vietnamese** MCQ ([Evaluating Symbol Binding for Vietnamese General Education, arXiv:2310.12059](https://arxiv.org/html/2310.12059), GPT-4 90.9% on ViMMRC 1.0 via symbol binding).
- **If you do score cloze-style, normalize.** [Holtzman et al. 2021, "Surface Form Competition"](https://aclanthology.org/2021.emnlp-main.564/) ([arXiv](https://arxiv.org/abs/2104.08315)): PMI_DC — score P(choice|question)/P(choice|domain-prompt) — consistently beats raw and length-normalized probability across GPT-2/3 families on zero-shot MC (typical gains 2–10 pts per dataset). Counterpoint: [arXiv:2305.14596](https://arxiv.org/pdf/2305.14596) shows normalization "can be ineffective or even detrimental for some LMs," and that simply **putting the choices in the prompt + 1 in-context example eliminates most surface-form competition** — which your CoT prompt already does. The [EleutherAI harness convention](https://blog.eleuther.ai/multiple-choice-normalization/) is byte-length normalization (`acc_norm`); note the [char-vs-byte discrepancy issue](https://github.com/EleutherAI/lm-evaluation-harness/issues/3278) matters for Vietnamese (multi-byte diacritics) — use **byte**-length if you implement it.
- **First-token logprob over letters is a known trap on chat models.** ["My Answer is C"](https://aclanthology.org/2024.findings-acl.441/) ([arXiv:2402.14499](https://arxiv.org/abs/2402.14499)): first-token probabilities mismatch the model's actual text answer at rates **up to >60%** on instruction-tuned models (preambles, refusal styles). [Look at the Text (arXiv:2404.08382)](https://arxiv.org/pdf/2404.08382) confirms text answers are *more robust* than first-token probs. Mitigation: read the letter distribution **at the exact position after a forced `ANSWER:` prefix following the model's own CoT**, not at response start.
- **Does it beat generative CoT for knowledge questions?** On knowledge-retrieval questions, yes/tie ([Sprague et al.](https://arxiv.org/abs/2409.12183): direct ≈ CoT on non-symbolic MMLU). On your reasoning-heavy mix, no ([MMLU-Pro](https://arxiv.org/abs/2406.01574): CoT >> direct with 10 options; your own 87.26 vs 77.11).

**llama-cpp-python feasibility:** yes, with caveats.
- `create_completion` and `create_chat_completion` accept `logprobs`/`top_logprobs` ([API reference](https://llama-cpp-python.readthedocs.io/en/latest/api-reference/)), **but** the OpenAI-style logprobs path requires `Llama(..., logits_all=True)`, which computes logits at every prompt position — slow and memory-heavy with Gemma's ~262k vocab (~1MB per context position), and has known off-by-one/perf issues ([issue #1983](https://github.com/abetlen/llama-cpp-python/issues/1983), [llama.cpp #6423](https://github.com/ggml-org/llama.cpp/issues/6423)).
- **Cheap correct path (recommended):** with default `logits_all=False`, the final-position logits are always available via the low-level API (`llm.eval(tokens)` then `llm.scores[llm.n_tokens-1]` / `Llama.logits_to_logprobs`). One forward pass of `prompt + CoT + "ANSWER:"` gives you the full next-token distribution over the letter tokens A–J for free. For full-continuation cloze scoring, eval the shared prefix once (KV-cached), then decode each choice's tokens one step at a time reading logits per step — cost ≈ generating len(choice) tokens per option, no `logits_all` needed.

## (b) Hybrid: CoT first, then score choices conditioned on the reasoning

This is the highest-leverage cheap upgrade:

1. Keep your greedy CoT. Append `ANSWER:` and read the **letter-token logit distribution** instead of regex-extracting. Fixes all extraction failures and "model wrote two letters" cases at zero marginal cost.
2. The margin between top-1 and top-2 letter probability is a strong correctness signal: [Wang & Zhou 2024, "Chain-of-Thought Reasoning Without Prompting" (arXiv:2402.10200)](https://arxiv.org/abs/2402.10200) show answer-token probability disparity reliably tracks the presence of correct reasoning and answer correctness. [Kadavath et al. 2022 (arXiv:2207.05221)](https://arxiv.org/abs/2207.05221) similarly show self-evaluation probabilities are well-calibrated for ~50B models and improve further when the model sees multiple of its own samples.
3. Use that confidence to **route**: high-margin → accept (majority of questions, no extra cost); low-margin → escalate to #2/#3/#4 below. This is the adaptive/confidence-aware self-consistency pattern: [Aggarwal et al. 2023 (Adaptive-Consistency)](https://arxiv.org/html/2511.09345v2) report up to **7.9× fewer samples at <0.1% accuracy loss** vs fixed-budget self-consistency; recent variants ([Dynamic SC, arXiv:2408.17017](https://arxiv.org/html/2408.17017v1), [Difficulty-Adaptive SC, arXiv:2408.13457](https://arxiv.org/html/2408.13457v3)) replicate.

For the escalated subset, full self-consistency is the best-validated accuracy buyer: [Wang et al. 2022 (arXiv:2203.11171)](https://arxiv.org/abs/2203.11171) report **+3.9 ARC-Challenge, +6.4 StrategyQA, +17.9 GSM8K** (40 sampled paths; the paper's scaling curves show most of the gain arrives by 5–10 paths). With k=5–8 at T≈0.7 on only the ~20–30% low-confidence questions, total compute ≈ 1.3–1.8× — well inside the 10-pt time budget, with the largest expected accuracy gain of any option here (+2 to +4 overall).

## (c) Self-verification / "are you sure" rounds — DO NOT

- [Huang et al., ICLR 2024, "LLMs Cannot Self-Correct Reasoning Yet" (arXiv:2310.01798)](https://arxiv.org/abs/2310.01798): intrinsic self-correction **reduces** accuracy — GPT-4 GSM8K 95.5→91.5→89.0 over two rounds; GPT-3.5 CommonsenseQA **75.8→38.1** after one round. Models flip correct→incorrect more often than the reverse.
- [FlipFlop experiment (arXiv:2311.08596)](https://arxiv.org/abs/2311.08596): challenger turns ("are you sure?") cause answer flips **46%** of the time and average accuracy deterioration of **−17%** across 10 LLMs; Sharma et al. 2023 ([arXiv:2310.13548](https://arxiv.org/abs/2310.13548)) traced this sycophancy to preference-trained models. A 26B open chat model will be at least as sycophantic as the models tested.
- Safe substitutes: (i) **P(True)-style scoring** — append "Is the proposed answer correct? (True/False)" and read the True/False logits ([Kadavath et al.](https://arxiv.org/abs/2207.05221)); use it only to *route to escalation*, never to flip directly; (ii) **fresh independent re-solve + vote** (self-consistency) rather than showing the model its own answer.

## (d) Two-stage answer + critique: same model vs different model

- Same-model critique = the negative results in (c).
- Cross-model: [Du et al. 2023, Multiagent Debate (ICML 2024, arXiv:2305.14325)](https://arxiv.org/abs/2305.14325) report **MMLU 71.1→74.2 (+3.1)** and +5–10 absolute on GSM8K with 3 agents × 2 rounds — but that is ~6× compute with equal-strength agents. With a *weaker* judge (Qwen3.5-9B judging Gemma-26B) expect much less: [Great Models Think Alike (arXiv:2502.04313)](https://arxiv.org/pdf/2502.04313) shows judge/ensemble gains shrink as model errors correlate and as the judge is weaker than the solver. Medical-MCQ consensus loops of 3 strong models gained **7–15 pts** ([ICE, ScienceDirect 2025](https://www.sciencedirect.com/science/article/abs/pii/S0010482525010820)) — not reproducible with one 26B + one 9B.
- **Practical design:** don't use Qwen as a *critic* of Gemma's reasoning (weak-judge + sycophancy-by-proxy). Use it as an **independent second solver** on the low-confidence subset; if Qwen agrees with Gemma → accept; if it disagrees → tie-break with Gemma self-consistency votes or letter-logit margins. Independent-solve-and-vote is the mechanism that drives both debate and ICE gains, at a fraction of the cost. Expected +0.5–1.5 overall since it only touches residual errors.

## (e) Elimination prompting for negation/EXCEPT questions

- **Generative elimination is a documented loser.** [Balepur et al. 2024, "It's Not Easy Being Wrong" (arXiv:2311.07532)](https://arxiv.org/html/2311.07532): CoT process-of-elimination underperforms direct CoT on *every* model × dataset tested — gaps of **5.7 to 14.0 points** (e.g., GPT-3.5 CSQA 93.7 vs 85.3; Falcon-180B CSQA 92.6 vs 78.6). Crucially for EXCEPT questions: they find misaligned rationales concentrate on *negated* questions — PoE is itself negated reasoning, so EXCEPT+PoE is "double negation" the models handle worst. Do **not** add a global "eliminate wrong answers first" instruction.
- **Scoring-based elimination works only in the logprob regime.** [Ma & Du 2023, POE (EMNLP 2023, arXiv:2310.15575)](https://aclanthology.org/2023.emnlp-main.273.pdf): mask the lowest-scoring options, re-score the rest — **+4.8 avg over the best baseline (56.1 vs 51.3)** across 8 tasks, **+13.8 on logical deduction**, with FLAN-T5-class scorers. If you adopt hybrid choice-scoring (#5), a one-line POE variant (drop bottom-half options, re-ask the CoT with the survivors) is cheap and language-agnostic, and is the only elimination flavor with positive evidence. Newer "eliminate-then-select" frameworks report gains in educational QA ([Springer 2025](https://link.springer.com/article/10.1007/s44443-025-00122-2)) but on the strength of the Balepur result, restrict any elimination step to the re-scored/escalation path, not the main pass.
- Also fix the cheap bias issue while you're there: [Zheng et al., ICLR 2024 (arXiv:2309.03882)](https://arxiv.org/abs/2309.03882) — selection bias moves accuracy by up to **±6–15 points** depending on where the gold answer sits; **PriDe** (estimate letter-prior on ~5% of questions by permutation, divide it out) gives ~**+1 pt** at 1.15× cost, full cyclic permutation +2.6 at 4×. On a Q4 26B model expect the prior to be non-trivial; PriDe is label-free and language-agnostic.

---

## Recommended pipeline (expected 87.26 → ~91–93)

1. **Pass 1 (all 2000):** current greedy CoT → forced `ANSWER:` → read letter-logit distribution (low-level API, no `logits_all`). Record margin. (+0.5–1.5)
2. **Route:** margin above threshold (tune on public set) → final. Below → escalate (~20–30% of Qs).
3. **Escalation:** k=5–8 CoT samples at T≈0.7 with option-order shuffled per sample (kills selection bias and buys SC simultaneously), majority vote over letters mapped back through the permutation; early-stop when one answer leads 0.95-style ([Adaptive-Consistency](https://arxiv.org/html/2511.09345v2)). (+2–4)
4. **Residual ties:** Qwen3.5-9B independent solve as extra vote. (+0.5–1.5)
5. Never include "are you sure" / self-critique turns; never use generative elimination as the default prompt.

Sources: [Holtzman et al. 2021](https://arxiv.org/abs/2104.08315) · [Robinson & Wingate 2022](https://arxiv.org/abs/2210.12353) · [Vietnamese MCSB 2310.12059](https://arxiv.org/html/2310.12059) · [Sprague et al. 2024](https://arxiv.org/abs/2409.12183) · [MMLU-Pro](https://arxiv.org/abs/2406.01574) · [My Answer is C](https://arxiv.org/abs/2402.14499) · [Look at the Text](https://arxiv.org/pdf/2404.08382) · [SFC counterpoint 2305.14596](https://arxiv.org/pdf/2305.14596) · [EleutherAI normalization](https://blog.eleuther.ai/multiple-choice-normalization/) · [harness #3278](https://github.com/EleutherAI/lm-evaluation-harness/issues/3278) · [llama-cpp-python API](https://llama-cpp-python.readthedocs.io/en/latest/api-reference/) · [llama-cpp-python #1983](https://github.com/abetlen/llama-cpp-python/issues/1983) · [llama.cpp #6423](https://github.com/ggml-org/llama.cpp/issues/6423) · [Self-Consistency](https://arxiv.org/abs/2203.11171) · [CoT-decoding 2402.10200](https://arxiv.org/abs/2402.10200) · [Kadavath 2022](https://arxiv.org/abs/2207.05221) · [Adaptive-Consistency](https://arxiv.org/html/2511.09345v2) · [Huang et al. ICLR 2024](https://arxiv.org/abs/2310.01798) · [FlipFlop](https://arxiv.org/abs/2311.08596) · [Du et al. debate](https://arxiv.org/abs/2305.14325) · [Great Models Think Alike](https://arxiv.org/pdf/2502.04313) · [ICE ensemble](https://www.sciencedirect.com/science/article/abs/pii/S0010482525010820) · [Balepur et al. 2311.07532](https://arxiv.org/html/2311.07532) · [POE 2310.15575](https://aclanthology.org/2023.emnlp-main.273.pdf) · [Eliminate-then-select](https://link.springer.com/article/10.1007/s44443-025-00122-2) · [PriDe 2309.03882](https://arxiv.org/abs/2309.03882)


---

# REPORT: ensemble-routing

# Ensembles + Compute Routing for Offline MCQ: Research Report

**Goal:** 87.26 → 93+ on 2000 Vietnamese-heavy MCQs (4-10 choices), offline, one 48GB GPU, Gemma 4 26B A4B QAT Q4_0 + optional Qwen3.5 ≤9B via llama.cpp. Accuracy 80pts dominant, time 10pts secondary.

---

## (a) Heterogeneous LLM ensembles on MCQ — fusion rules and effect sizes

**Sampling + majority vote scales reliably.** ["More Agents Is All You Need"](https://arxiv.org/abs/2402.05120) (Li et al., 2024) shows plain sampling-and-voting monotonically improves accuracy with ensemble size; at ~15 samples Llama2-13B matches Llama2-70B, and gains correlate with task difficulty (hard questions gain most, saturating ~10-20 samples). This is the single best-replicated effect in this space.

**Heterogeneous (multi-model) ensembles beat the best single model by +1-6pp on MCQ.** The [LLM-Synergy study (JMIR 2025)](https://www.jmir.org/2025/1/e70080) on medical MCQ: boosting-weighted majority vote gave +3.81pp on MedMCQA and +0.64pp on PubMedQA over the best member; cluster-based dynamic model selection gave +5.98pp / +1.09pp / +0.87pp (MedMCQA / PubMedQA / MedQA). The earlier ["One LLM is not Enough"](https://pmc.ncbi.nlm.nih.gov/articles/PMC10775333/) preprint shows the same pattern. Caveat: members were of comparable accuracy — ensembling a much weaker model with equal weight can hurt (Condorcet logic); weight votes by per-model dev-set accuracy.

**Fusion rule ranking (empirical consensus):**
1. **Unweighted/normalized majority vote over final answers** — the [self-consistency paper](https://arxiv.org/abs/2203.11171) (Wang et al., ICLR 2023) found plain majority vote matches or beats logprob-weighted voting and clearly beats "sample-and-rank by sequence logprob" (max-prob over whole generations is length-biased — confirmed independently by [Gupta et al. 2024](https://arxiv.org/abs/2404.10136)).
2. **Accuracy-weighted vote** when members differ in strength (LLM-Synergy above, +1-3pp over unweighted).
3. **Max answer-letter probability** is best used as a *tie-breaker*, not a primary fusion rule.
4. **Abstain/escalate when the vote margin is below threshold** — [voting ensembles with abstention](https://arxiv.org/abs/2510.04048) (2025) shows the dominant-answer share is a strong trust signal: answers above threshold are dramatically more reliable, which is exactly the routing signal you need (see §c).

## (b) Is Qwen3.5 ≤9B strong enough to add signal next to Gemma 4 26B A4B?

**Yes — it is at near-parity, not a junior partner.** Cross-checked numbers:

| Benchmark | Gemma 4 26B A4B | Qwen3.5-9B |
|---|---|---|
| MMLU-Pro | 82.6 | 82.5 |
| GPQA Diamond | 82.3 | 81.7 |
| MMMLU (multilingual MMLU) | **86.3** | 81.2 |
| MMLU-Redux | — | 91.1 |

Sources: [Maniac benchmark-by-size comparison](https://www.maniac.ai/blog/qwen-3-5-vs-gemma-4-benchmarks-by-size), [llm-stats Qwen3.5-9B](https://llm-stats.com/models/compare/gemma-3-27b-it-vs-qwen3.5-9b), [XDA on Qwen3.5-9B](https://www.xda-developers.com/qwen-3-5-9b-tops-ai-benchmarks-not-how-pick-model/) (notes Qwen3.5-9B beats the 13x-larger GPT-OSS-120B on MMLU-Pro 82.5 vs 80.8 and MMMLU 81.2 vs 78.2), [Qwen3.5-9B HF card](https://huggingface.co/Qwen/Qwen3.5-9B). In the same family the smaller MoE class also favors Qwen on reasoning (Qwen3.5-4B MMLU-Pro 79.1 vs Gemma 4 E4B 69.4).

**Implications:** (1) The two models are close enough that a 2-model vote satisfies the "comparable accuracy" condition for ensemble gains; (2) they come from different labs/data/architectures (Gemma MoE vs Qwen hybrid Gated-DeltaNet+MoE), so errors should be well-decorrelated — diversity is what drives heterogeneous-ensemble gains; (3) Gemma keeps a **+5pp multilingual edge (MMMLU 86.3 vs 81.2)**, so for Vietnamese keep **Gemma as the primary/tie-break authority** and Qwen as the second opinion. Also note your QAT Q4_0 Gemma loses little vs bf16: Google's QAT cuts the Q4_0 perplexity drop by ~54% vs naive PTQ ([Gemma 3 QAT blog](https://developers.googleblog.com/en/gemma-3-quantized-aware-trained-state-of-the-art-ai-to-consumer-gpus/), [Gemma 4 QAT blog](https://blog.google/innovation-and-ai/technology/developers-tools/quantization-aware-training-gemma-4/)) — so quantization is not your accuracy bottleneck.

## (c) Cascade / tiered routing without calibrated confidence

Three escalation signals that work *uncalibrated*, ranked by evidence strength:

1. **Answer agreement / consistency (best).** [Mixture-of-Thoughts cascades](https://arxiv.org/abs/2310.03094) (Yue et al., ICLR 2024) escalate only when sampled answers disagree (and/or CoT vs program-of-thought disagree): matched GPT-4-only accuracy (~92.9 vs 93.1) at **40% of the cost** across six reasoning benchmarks. The same signal drives [Adaptive-Consistency](https://arxiv.org/abs/2305.11860) (Aggarwal et al., EMNLP 2023): stop sampling once a Dirichlet posterior says the leading answer is settled — **up to 7.9x fewer samples at <0.1pp accuracy loss** over 17 datasets. Agreement-of-2 across *different models* is the cheapest variant of this: if Gemma and Qwen agree, the answer is very likely right; nearly all recoverable errors live in the disagreement set.
2. **Max softmax probability (MSP) on the answer letter.** [Probabilities of chat LLMs are miscalibrated but still predict correctness on MCQ](https://arxiv.org/abs/2402.13213) (2024): across 15 chat LLMs, MSP discriminates right from wrong answers significantly above chance in 99/100 model-dataset pairs (78/80 for max-logit) *despite* miscalibration — calibration and ranking power are decoupled, so you don't need calibration, just a threshold tuned on a small dev set. llama-cpp-python exposes `logprobs`, so this is free. [Token-level cascades](https://arxiv.org/abs/2404.10136) (Gupta et al., 2024) add a warning: avoid whole-sequence logprob (length bias); use the answer-token probability or token-level quantiles. If you can label ~300-500 dev questions, a tiny isotonic fit on this signal is near-optimal — [UCCI](https://arxiv.org/abs/2605.18796) cut cost 31% at quality parity in a 4B→12B cascade this way.
3. **Question-type heuristics (weakest, but free).** Escalate by surface features: number of options (selection bias and noise grow with 6-10 options), presence of math/calculation, negation ("KHÔNG", "NGOẠI TRỪ"), and question length. Vietnamese exam data shows exactly this difficulty split — ChatGPT-class models score 48-69% on calculation subjects vs 56.5-92.4% on language subjects on VNHSGE ([Dao et al., 2023](https://arxiv.org/abs/2306.09170)). Use as a prior to pre-allocate samples, not as the sole gate.

**Expected savings:** consistency-gated cascades repeatedly hit **equal accuracy at 40-60% of full-blast compute** (MoT 40%, Adaptive-Consistency 3.3-7.9x sample reduction, [survey](https://arxiv.org/html/2603.04445v2)). For you the cascade runs in reverse (spend *more* on hard items): same math, the disagreement subset is where extra samples buy accuracy.

## (d) Test-time compute scaling for small models, llama.cpp-compatible

- **Self-consistency (parallel, temp ~0.7-1.0, majority vote):** the canonical numbers from [Wang et al.](https://arxiv.org/abs/2203.11171): +17.9pp GSM8K, +12.2 AQuA (MCQ), +11.0 SVAMP, +6.4 StrategyQA, +3.9 ARC-Challenge, consistent across model scales. On a strong model already at 87%, expect **+1.5-4pp overall**, concentrated on the uncertain subset. Fully offline; needs only `temperature>0` and answer extraction.
- **Compute-optimal allocation:** [Snell et al. 2024](https://arxiv.org/abs/2408.03314) show adaptive per-question allocation beats uniform best-of-N by **>4x efficiency**, and a small model with test-time compute can beat a 14x larger model on questions where it has non-trivial success rate — the theoretical license for "Qwen3.5-9B + samples" punching at 26B level. Difficulty-adaptive variants of SC confirm this ([DSC, NAACL 2025](https://aclanthology.org/2025.findings-naacl.383.pdf)).
- **Budget forcing (s1-style):** [s1](https://arxiv.org/abs/2501.19393) appends "Wait" to force longer thinking — sequential scaling lifted s1-32B from 50%→57% AIME24. Works in llama.cpp (it's just continued decoding), but gains concentrate in competition math; for knowledge-heavy MCQ parallel sampling dominates ([critical analysis](https://arxiv.org/pdf/2507.14419)). Use only as a last-tier tool on math items.
- **Best-of-N with verifier/reranker:** needs a reward model you don't have; majority vote is the verifier-free version and is the right choice here. Tool-integrated self-verification helps sub-3B models ([T1](https://arxiv.org/pdf/2504.04718)) but is unnecessary at 9-26B.
- **Throughput reality:** llama.cpp continuous batching (`--parallel N`) interleaves sequences and **shares the prompt KV across samples of the same question at zero extra prefill cost** ([llama.cpp discussion #4130](https://github.com/ggml-org/llama.cpp/discussions/4130)); reference servings show ~484 tok/s aggregate for a 7B on A100 with 8 parallel clients ([Resonance tutorial](https://resonance.distantmagic.com/tutorials/how-to-serve-llm-completions/), [batching guide](https://promptsicle.com/tips/boosting-llama-server-performance-with-batch-settings/)). k=8 samples of one question ≈ ~2-3x wall-clock of one sample, not 8x.

## (e) Vietnamese MCQ evidence — what actually matters

- **Symbol binding (answer-letter prediction) works for strong models on Vietnamese:** GPT-4 hits 90.86-91.63% on ViMMRC 1.0, 84.22-85.84% on ViMMRC 2.0, but only 55.81-71.24% on national-exam STEM (ViGEText_17to23); small 7B-class models collapse (27-33%) ([symbol-binding study](https://arxiv.org/html/2310.12059)). Lesson: literary/RC items are "easy tier", **math/STEM exam items are the hard tail** — route compute there.
- **VNHSGE** (19k MCQs, 9 subjects): calculation subjects 48-69% vs language subjects 56.5-92.4% for ChatGPT-class ([VNHSGE dataset](https://www.researchgate.net/publication/370948070_VNHSGE_VietNamese_High_School_Graduation_Examination_Dataset_for_Large_Language_Models), [Dao et al.](https://arxiv.org/abs/2306.09170)) — same difficulty split.
- **VMLU** (58 subjects, 4 difficulty tiers, MoET-sourced exams) is the closest public analog to your test distribution; the [ACL 2025 toolkit paper](https://aclanthology.org/2025.acl-long.563/) explicitly reports that **prompt design materially shifts VMLU scores** and evaluates Llama-3/Qwen2.5/GPT-4 — few-shot Vietnamese exemplars + Vietnamese instruction phrasing matter. [Vietnamese-trained models compete with Llama-3-70B on VMLU](https://www.aiforvietnam.org/vietnam-generative-ai-progress/) mostly via Vietnamese-data tuning — not available to you, so prompt + ensemble is your lever. ([ViMMRC 2.0](https://arxiv.org/abs/2303.18162), [recent Vietnamese MRC eval](https://arxiv.org/html/2503.18062v1) confirm GPT-4-class CoT+few-shot dominate.)
- **Selection bias is real and worse with more options:** LLMs systematically over-pick certain letter positions; [PriDe](https://arxiv.org/abs/2309.03882) (ICLR 2024) removes the prior over option-ID tokens estimated from ~5% of samples, matching full permutation-debiasing at ~negligible cost, typically +1-2pp (more on heavily biased models, and your 4-10-choice format amplifies the issue). A cheaper in-pipeline variant: make one of your self-consistency samples a **choice-order permutation** — vote across permutations kills position bias for free.

---

## Recommended architecture (2000 Q, 48GB GPU)

VRAM fits both models simultaneously: Gemma 4 26B A4B QAT Q4_0 ≈ ~15-18GB + KV, Qwen3.5-9B Q4_K_M/Q5 ≈ 6-8GB + KV. Run two llama.cpp server instances with continuous batching (`--parallel 8-16`).

**Tier 1 — dual greedy pass (every question, ~2x current cost, heavily batched):**
- Gemma CoT @ T=0 (your current 87.26 baseline) **+ record answer-letter logprob (MSP)**.
- Qwen3.5-9B CoT @ T=0 (cheap; hybrid-attention 9B decodes fast).
- **Lock in** if (Gemma == Qwen) AND Gemma MSP ≥ threshold τ (tune τ on a self-made dev split from any provided training data; without one, τ≈0.8 on the letter token is a sane default per the [MSP paper](https://arxiv.org/abs/2402.13213)). Expect ~65-80% of items locked at ~94-97% subset accuracy (MoT-style agreement sets run this high).

**Tier 2 — self-consistency burst (the ~20-35% disagreement/low-MSP set):**
- Gemma: k=8 samples, T≈0.8, top-p 0.95; include 1-2 **choice-order-permuted** prompts among the k (PriDe-lite). Qwen: k=4 samples.
- **Accuracy-weighted vote** across all 14 trajectories (weight Gemma ≈ 1.0, Qwen ≈ 0.8, or dev-measured accuracies); Adaptive-Consistency early stop (quit sampling once leader is statistically settled — 3-8x sample savings).
- Tie-break by Gemma's mean answer-letter MSP.

**Tier 3 — residual ties (~2-5%):** math-flagged items get one s1-style "Wait"-extended Gemma generation (longer budget); others get full choice-permutation majority on Gemma. Never abstain — pick Gemma's argmax letter by logprob over the valid letter set (also your guaranteed-valid-output fallback for extraction failures).

**Expected gains (literature-anchored, multiplicative overlap discounted):** SC on the hard subset +2-3.5pp overall; heterogeneous 2-model vote +1-2pp; permutation/position debias +0.5-1.5pp; hardened letter extraction via constrained logprob fallback +0.3-1pp (you already saw 77.11→87.26 from extraction alone — residual parse failures are cheap points). Net estimate **+4-7pp → 91.5-94**. 93 is reachable but sits at the optimistic-middle of the range; the k in Tier 2 is your dial — raise it (More-Agents scaling) until your time budget bites. Total compute ≈ 2.5-4x a single pass, but with shared-prefix KV and continuous batching, wall-clock ≈ 2-3x — a small sacrifice of the 10-pt time score for the dominant 80-pt accuracy score.

**Risks:** (1) Qwen3.5-9B's Vietnamese is ~5pp behind Gemma (MMMLU) — never let Qwen alone override Gemma; it only contributes through agreement/votes. (2) Vote weights and τ tuned on non-representative dev data can underperform — keep unweighted majority as the fallback if no dev set exists. (3) Budget forcing helps mainly math; don't apply globally ([analysis](https://arxiv.org/pdf/2507.14419)).

**Sources:** [Self-Consistency (Wang et al.)](https://arxiv.org/abs/2203.11171) · [More Agents Is All You Need](https://arxiv.org/abs/2402.05120) · [MoT Cascades (Yue et al.)](https://arxiv.org/abs/2310.03094) · [Adaptive-Consistency](https://arxiv.org/abs/2305.11860) · [Token-level cascade uncertainty (Gupta et al.)](https://arxiv.org/abs/2404.10136) · [UCCI calibrated cascades](https://arxiv.org/abs/2605.18796) · [Cascade survey](https://arxiv.org/html/2603.04445v2) · [Miscalibrated-but-predictive MSP](https://arxiv.org/abs/2402.13213) · [Voting ensembles + abstention](https://arxiv.org/abs/2510.04048) · [LLM-Synergy (JMIR)](https://www.jmir.org/2025/1/e70080) · [One LLM is not Enough](https://pmc.ncbi.nlm.nih.gov/articles/PMC10775333/) · [PriDe / MCQ selection bias](https://arxiv.org/abs/2309.03882) · [Snell et al. test-time compute](https://arxiv.org/abs/2408.03314) · [s1 budget forcing](https://arxiv.org/abs/2501.19393) · [s1 critique](https://arxiv.org/pdf/2507.14419) · [T1 small-model TTC](https://arxiv.org/pdf/2504.04718) · [DSC difficulty-adaptive SC](https://aclanthology.org/2025.findings-naacl.383.pdf) · [Qwen3.5 vs Gemma 4 benchmarks](https://www.maniac.ai/blog/qwen-3-5-vs-gemma-4-benchmarks-by-size) · [llm-stats comparison](https://llm-stats.com/models/compare/gemma-3-27b-it-vs-qwen3.5-9b) · [XDA Qwen3.5-9B](https://www.xda-developers.com/qwen-3-5-9b-tops-ai-benchmarks-not-how-pick-model/) · [Qwen3.5-9B HF](https://huggingface.co/Qwen/Qwen3.5-9B) · [Qwen3 TR](https://arxiv.org/pdf/2505.09388) · [Gemma 4 QAT blog](https://blog.google/innovation-and-ai/technology/developers-tools/quantization-aware-training-gemma-4/) · [Gemma 3 QAT blog](https://developers.googleblog.com/en/gemma-3-quantized-aware-trained-state-of-the-art-ai-to-consumer-gpus/) · [VMLU](https://vmlu.ai/) · [VMLU ACL 2025](https://aclanthology.org/2025.acl-long.563/) · [VNHSGE](https://arxiv.org/abs/2306.09170) · [Vietnamese symbol binding](https://arxiv.org/html/2310.12059) · [ViMMRC 2.0](https://arxiv.org/abs/2303.18162) · [Vietnamese MRC eval 2025](https://arxiv.org/html/2503.18062v1) · [llama.cpp batching #4130](https://github.com/ggml-org/llama.cpp/discussions/4130) · [llama-server batching](https://promptsicle.com/tips/boosting-llama-server-performance-with-batch-settings/)