# ≤5B rules pivot + config-driven model policy — 2026-06-16

Supersedes the family/size half of [contest-rules-bang-c-2026-06-13.md](contest-rules-bang-c-2026-06-13.md).
The output contract (Docker `/data/*_test.csv|json` → `/output/pred.csv` `qid,answer`), the scoring
surface (Accuracy 80 / Time 10 / Idea 10), and the deadlines from that note are UNCHANGED.

## What the organisers changed

New BTC announcement (relayed by owner, 2026-06-16):

- **Size cap: ≤5B params.** Open model choice now — not just Gemma-4 / Qwen3.5. BTC's clarification
  when asked: *"vẫn sử dụng được các mô hình khác, lưu ý phần kích thước"* = you may use other
  models, **mind the size**. So the binding constraint is the 5B ceiling, not a family allowlist.
- **Single model.** One model end-to-end; no model ensembles.
- **No external models / no search APIs.** Internet is isolated at eval time.
- **Fine-tuning by the contestant is expected** (the "Idea/optimization" score rewards it).
- **Collecting internet data for training is allowed** (do it in dev, bake results offline).

### Residual ambiguity we MUST resolve before committing a model

MoE total-vs-active: Gemma-4-26B-A4B is **26B total / 4B active**. If "≤5B" counts *total*,
the 26B MoE is **disqualified**; if it counts *active*, it qualifies. We do not have a written BTC
answer on this yet. **Plan for the strict reading (total ≤ 5B)** until clarified — i.e. assume the
26B MoE is out and a dense ≤5B is the contestant.

Reranker question: a BGE/Qwen reranker is an embedding/scoring model, not a generative "model" in
the single-model sense. It was explicitly eligible under the old rules; under the new wording it is
*probably* still fine as a retrieval component, but flag it as a clarify-before-ship item.

## Why this forced a refactor (not a one-line edit)

The allowlist used to be **hardcoded** in `model_inventory.classify_model` (`if "gemma-4" in id…`,
`if "qwen3.5" in id…`). Pivoting families/caps meant editing Python — exactly the "hardcore code"
the owner told us to stop doing, and against AGENTS.md (config-first, no god functions). A rules
change from the organisers should be a **data edit**, not a code change.

## The config-driven model policy (shipped 2026-06-16)

`model_inventory.py` now expresses the allowlist as DATA:

- `FamilyRule(aliases: tuple[str,...], max_params_b: float | None)` — one allowed family; `None` cap
  = no size limit; alias `"*"` = wildcard (any model, size-gated only).
- `ModelPolicy(llm, embedding, count_active_for_moe)` — the whole allowlist. `count_active_for_moe`
  flips MoE size parsing between the `aNb` (active) and largest `Nb` (total) token — this is the one
  knob that settles the ambiguity above the day BTC answers it.
- `policy_from_config(config)` reads `runtime.model_policy`; falls back to `DEFAULT_POLICY`
  (legacy Gemma-4 any-size + Qwen3.5 ≤9B + BGE-M3/Qwen-Rerank) when absent.
- `classify_model(model_id, *, policy=DEFAULT_POLICY)` — generic; no per-model branch.
- `_params_b(id, *, active)` parses size from the id (`a4b`→4 when active, else max `Nb` token).

`config.model_policy` accessor added; `validate_runtime_model` (run.py) now uses
`policy_from_config(config)` and builds its error message from the policy (no hardcoded family names).
`configs/default.json` + `resources/default.json` carry a `runtime.model_policy` block that
**reproduces the legacy semantics exactly** (proven: `policy_from_config(default) == DEFAULT_POLICY`).

### How to PIVOT to ≤5B (no code change — this is the whole point)

Edit `runtime.model_policy` in the ship config to a single size-gated wildcard family:

```json
"model_policy": {
  "count_active_for_moe": false,
  "llm_families": [{"aliases": ["*"], "max_params_b": 5.0}],
  "embedding_families": [{"aliases": ["bge-m3"]}, {"aliases": ["qwen-rerank", "qwen_rerank"]}]
}
```

`count_active_for_moe: false` = strict total-param reading (26B MoE blocked). Flip to `true` only if
BTC confirms active-param counting. Want to keep a family allowlist instead of a wildcard? List the
families explicitly with the 5.0 cap. Either way: **config edit, zero Python.**

Tests covering this: `test_default_config_yields_legacy_model_policy`,
`test_model_policy_is_config_driven_extensible`,
`test_model_policy_counts_active_params_when_configured` (tests/test_contract.py). 257 green, ruff clean.

## Candidate ≤5B contestants (research 2026-06-16, pre-fine-tune)

- **Qwen3-4B-Instruct-2507** — dense 4B, no total/active ambiguity, strong multilingual incl. VI.
  Safest pick. **Baseline measurement still PENDING** (see below).
- Phi-4-mini-reasoning (~3.8B) — MATH-500 ~94.6 but weak Vietnamese.
- VibeThinker-3B — reasoning specialist; large knowledge/multilingual gap (GPQA −20–40pt).
- Gemma-3n-E4B — 8B total / 4B "effective"; **risky** under a total-param reading.
- PhoGPT-4B — VN-native but weak reasoning.

Knowledge does NOT compress into a ≤5B model the way it sits in 26B → **RAG / corpus vault becomes
essential**, not optional. Fine-tuning is now required, not a nice-to-have.

## Qwen3-4B baseline test — MEASURED 2026-06-16

Owner confirmed ≤5B is binding → ran the baseline to completion. Rebuilt `neko-mtp-context.tar.gz`
from current `src/` (config-driven validator), config-driven ≤5B wildcard policy via overlay (real id
`qwen3-4b-instruct-2507`, no relabel). RTX 3090, Q5_K_M GGUF, self-consistency **k=1, NO fine-tune**,
450-q labeled proxy dev set. **0 fallbacks** (Qwen follows the `ANSWER:` format cleanly). wall 3845s
= **8.5s/q**. Pod self-terminated; balance $2.06→$1.77 (~$0.29).

| Cluster | Qwen3-4B k=1 | Gemma-26B battery | Δ |
|---|---|---|---|
| quant   | 73.91% (85/115)  | 86.67% | **−12.76** |
| civics  | 78.67% (118/150) | 91.67% | **−13.00** |
| reading | 85.41% (158/185) | 91.67% | **−6.26** |
| OVERALL | **80.22% (361/450)** | ~90% | **~−10** |

**Read:** the gap is exactly where theory predicts — knowledge-bound clusters bleed most (civics −13
pure recall, quant −12.76 knowledge+method), comprehension-bound reading bleeds least (−6.26). This is
the **floor before recovery levers**, and it CONFIRMS the pivot thesis: a ≤5B can't hold the knowledge,
so the path back to ~90% is **(1) RAG fact-vault** (targets civics; already +3 leaderboard on Gemma,
bigger upside on a 4B that knows less), **(2) method-RAG** (targets quant; already +2 on Gemma quant),
**(3) fine-tuning** (now required + Idea-rewarded; recovers general knowledge/format/domain), and
optionally **(4) k>1 self-consistency** on quant. Reading (−6) is the most recoverable. Raw 80.22% is
NOT competitive as-is, but it is a healthy, format-clean base to build the recovery stack on.

Speed note (Time axis): 8.5s/q at k=1 with a 2048-token budget is not a 4B win yet vs Gemma-26B-A4B —
a smaller model should get faster with a tighter token budget / shorter prompts; defer to a dedicated
Time-tuning pass.

## Recovery measurement (a): RAG on Qwen3-4B — DIRECTIONALLY POSITIVE but CONFOUNDED (2026-06-16)

Owner greenlit (a). Same dense-gate machinery as the Gemma ship (rag-gated: BM25→BGE-reranker gate,
inject chunk as fallible reference) but LLM = Qwen3-4B, corpus = **combined** (37 current-fact + 30
method = 67), reranker **thr 0.4** (so both gates can fire), 450-q proxy, k=1, no fine-tune. A4000,
0 fallbacks, contract 100, wall 4060s, ~$0.32. Pod self-terminated; balance $1.77→$1.45.

| Cluster | +RAG | Qwen baseline | Δ | gate fires |
|---|---|---|---|---|
| quant   | 76.52% (88/115)  | 73.91% | +2.61 | 24 |
| civics  | 84.67% (127/150) | 78.67% | +6.00 | **2** |
| reading | 86.49% (160/185) | 85.41% | +1.08 | **91** |
| OVERALL | **83.33% (375/450)** | 80.22% | **+3.11** | 117/450 |

**DO NOT read this as "RAG +3 (or civics +6)".** Two real problems make the per-cluster deltas
untrustworthy as a clean RAG attribution:

1. **Sampling-noise confound.** Baseline and RAG are two SEPARATE k=1 runs at temp 0.8 with **no fixed
   seed** → the 333 non-gated questions draw DIFFERENT samples in each run → their answers differ by
   variance, not by RAG. The deltas mix RAG effect + run-to-run noise. Proof: **civics gained +6 (+9
   questions) on only 2 gate fires** — at most +2 is RAG, the other +7 is sampling noise. The civics
   number is essentially noise, NOT a RAG win.
2. **Gate over-fires at thr 0.4.** reading fired **91/185 (49%)** — the combined corpus + low threshold
   fires spuriously on reading passages (the ship used 0.85 precisely to avoid this). Net harmless here
   (+1.08, model ignores irrelevant refs) but wasteful (reranker cost) and risky.

**The trustworthy signal = quant +2.61** (24 fires concentrated where method helps; consistent with the
Gemma method-RAG +2). The robustness signal is solid: **RAG + ≤5B works end-to-end** (0 fallbacks,
config-driven validator + reranker-CPU + combined corpus all clean). Overall is directionally positive
but the clean RAG-attributable lift is modest (~+2–3, mostly quant/method), and the narrow fact-vault
**cannot** touch the broad civics −13 (only 2 fires → it's not the lever for general civics knowledge).

**To get a CLEAN number next (in priority order):**
1. **Seeded A/B** — run RAG-on vs RAG-off with a FIXED seed so non-gated questions are byte-identical →
   the delta is purely the gate effect. (Needs seed support on the local llama path — verify.)
2. **Threshold tuning / dual-gate** — gate-audit to stop reading over-firing; fact slice wants ~0.85,
   method slice ~0.4 → a single combined corpus + single threshold is the wrong design (use a dual gate
   or per-cluster routing), as the method-RAG note already flagged.
3. **Corpus expansion for broad civics** — the −13 is general civics/law/history the 4B lacks; the
   37-fact admin-reform vault can't fix it. Needs an authoritative broad knowledge corpus (gate-audited)
   — AND/OR fine-tuning, which is the bigger lever for parametric knowledge recovery.

## Fine-tuning on a regular M4 Mac (macOS)?

**Yes — LoRA/QLoRA on Apple Silicon via Apple's MLX (`mlx-lm`), no rented GPU needed for the train
step**, but it is RAM-bound:

- **M4 Pro / Max with 24–48GB unified memory**: comfortable for LoRA on a 4B model.
- **Base M4 16GB**: tight but doable with a 4-bit base + small LoRA rank + short sequences; expect to
  babysit memory and run slower.
- Renting a GPU (or free Colab/Kaggle T4/A100) is **faster and more reliable** for iteration; the Mac
  is fine for a final/low-volume run.
- Either way the **final artifact converts to GGUF** (llama.cpp) for the offline x86+CUDA Docker
  image — the eval container is not Apple Silicon, so training device ≠ serving device.
