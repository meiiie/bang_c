# RAG / lever analysis — measure-first, all from pre-existing runs (2026-06-18)

**TL;DR:** Investigated whether RAG/rerank or harness-polish can beat the un-FT base on the 450 proxy,
using runs that already existed (no new GPU). The nominal "RAG +3.11" is **mostly k=1 stochastic variance**,
and on a clean battery **RAG HURTS civics −5.00**. The only clean RAG signal is quant (+3, 0 broke ≈ +0.67pp
overall — within the noise band). The dominant issue is **k=1 variance (~30 questions flip run-to-run)**,
not a missing lever. **Qwen3-4B is at/near the ≤5B ceiling (~80–84). Recommendation: ship the base v0.7.1.**

## Distribution (proxy = THPT national-exam MCQ)
- quant (Hóa+Toán) 115, science (Lý/…) 185, civics (GDCD) 150. ~26% pure computation (RAG-useless),
  the rest is curriculum knowledge-APPLICATION (not obscure-fact retrieval). Likely mirrors private 2000q.

## Strategy comparison on the 450 proxy (per cluster, vs un-FT base 80.22)
| run | overall | quant | civics | science |
|-----|---------|-------|--------|---------|
| BASE qwen | 80.22 | 73.91 | 78.67 | 85.41 |
| RAG qwen (rag-gated thr0.4) | 83.33 (+3.11) | 76.52 (+2.61) | 84.67 (+6.00) | 86.49 (+1.08) |
| FT-v2 mcq | 80.22 (0) | −1.74 | −0.67 | +1.62 |
| FT-v1 mix | 75.78 (−4.44) | −14.78 | 0 | −1.62 |

## Variance audit — the RAG "+3.11" does not survive scrutiny
Only **30 questions** changed answer base↔RAG, but the gate fired **117** times:
| cluster | gate_fires | changed | fixed | broke | net |
|---------|-----------|---------|-------|-------|-----|
| quant | 24 | 6 | 3 | 0 | **+3 (clean)** |
| civics | 2 | 16 | 11 | 2 | +9 (**14/16 changes are NON-gate = pure k=1 variance**) |
| science | 91 | 8 | 4 | 2 | +2 (over-fires 91×, broke 2 = **false-positives**) |
- civics +6 is mostly run-to-run noise (gate fired on only 2 of the 16 changed). science gate over-fires.
- A +3.11 (=14 questions) is **inside the ±30-question k=1 variance band** → not attributable to RAG.

## Clean battery (120-q/cluster, strategy levers; note `31b` = >5B model, disqualified, ref only)
| cluster | self-consistency | k5vote | rag | 31b |
|---------|------------------|--------|-----|-----|
| civics | 91.67 | −0.83 | **−5.00** | +0.83 |
| quant | 86.67 | −0.83 | (router −7.50) | +2.50 |
| reading | 91.67 | +0.83 | — | +2.50 |
- On clean measurement **RAG hurts civics (−5)** — opposite of the proxy's variance-driven +6. Confirms the
  proxy civics gain was noise. k5-vote ≈ self-consistency (no clean win). Only more model capacity (>5B) helps.

## Verdict
- **Neither RAG (as built) nor harness-polish/k5 is a clean win.** RAG is net-marginal + false-positive-risky;
  not shippable as-is. The base is near the ≤5B ceiling.
- The one clean micro-signal = a **tight quant-only RAG gate** (+3, 0 broke ≈ +0.67pp), but it's within noise.
- **Ship base v0.7.1 (lb 83.59).** Per feedback-stop-low-ev-experiments, don't spend GPU on within-noise levers.
- If ever squeezing: (a) tight quant-only-gated RAG with generalization validation, or (b) a variance-controlled
  k>1 test — both modest, execution-heavy, diminishing returns. Not autonomous; owner's call.

## TIR (tool-integrated reasoning) on quant — MEASURED on Qwen-4B (2026-06-18), it HURTS
The harness ships a full TIR path (`prompting.build_tir_code_prompt`/`build_tir_answer_prompt` +
`tool_runtime.run_python`, offline sandbox), config-marked "pending real-model measurement". Ran BASE
self-consistency AND `--workflow tir` on the same 115 quant in one pod (env-controlled):
| run | quant acc | fixed | broke | net |
|-----|-----------|-------|-------|-----|
| BASE self-consistency | 74.78% (86/115) | — | — | — |
| **TIR (write+exec Python)** | **58.26% (67/115)** | 5 | 24 | **−19 (−16.52pp)** |
- TIR genuinely ran (`strategies={gemma_tir:68, gemma_tir_degraded:47}` — **41% degraded**; valid=True).
- Qwen-4B is **below the competence threshold** to write reliable Python for THPT math/chem → TIR breaks 24
  questions direct reasoning got right. "Weakest-improves-most" FAILS for code-writing TIR (Gemma-26B was
  "net-dead"; 4B is net-NEGATIVE). Run bee3kc43l / pod v19srdhbis3st2, ~$0.2.

## CONSOLIDATED — every accuracy lever measured; the base is the ceiling
| lever | clean result on proxy | ship? |
|-------|----------------------|-------|
| Fine-tune (v1 mix / v2 mcq) | −4.44 / +0.00 | no |
| RAG-gated | +3.11 nominal = variance; clean battery civics −5 | no |
| TIR on quant | **−16.52** | no |
| k5-vote vs self-consistency | ≈0 (±0.83) | no |
| **un-FT base self-consistency** | **80.22 proxy / 83.59 lb** | **YES** |
**Conclusion: SHIP base v0.7.1.** HarnessX-style adaptive routing, when *measured* on this reasoning-bound
≤5B MCQ task, does not help (TIR/RAG actively hurt) — it shines on agentic/tool benchmarks, not here. The
defensible Idea-axis story is the *empirical rigor itself*: a composable harness whose every lever was
held-out-measured, rejecting flashy-but-harmful complexity (TIR −16.52, RAG false-positives) — base
self-consistency is provably optimal for ≤5B AND fastest (best Time axis).

Scripts: `Temp/pod_mtp/{compare_strategies,rag_variance_audit,battery_levers,classify_rag_headroom}.py`
+ `run_tir_quant*.{sh,py}`. Fine-tune verdict: `notes/2026-06-18-finetune-verdict.md`.
