# ▶ RESUME HERE — next-session entry point (updated 2026-06-12, post GPU Q4 measurement)

Read this FIRST. It is self-contained: project identity, rules, current state, and how to
continue without losing context.

---

## ▶▶ LATEST STATE (2026-06-12) — read before the older sections below

- **Leaderboard now: 31B-Q4 = 88.12** (vs 26B-Q4 baseline 87.26 = +0.86pp real). **88.12 is
  NOT enough to advance** — the goal is to push accuracy HIGHER.
- **GPU Q4 measurement done** (RunPod, attended): 26B-Q4 88.2% / 31B-Q4 90.9% / Qwen3.5-9B
  84.9% on the 450-q labeled proxy. BUT the proxy **OVERESTIMATED** — proxy said 31B +2.7pp,
  the real leaderboard gain is only **+0.86pp**. LESSON: labeled proxies (ViGEText/ViMMRC)
  give DIRECTION not MAGNITUDE; the leaderboard is the only ground truth.
- **31B operational tail-risk:** 31B Q4 (~17.7GB) needs **≥40GB VRAM** — OOMs/stalls on 24GB
  (crashed a GPU this session). If the BTC judge GPU is 24GB a 31B Docker → 0 on the private
  test. **26B-A4B (MoE 14.4GB) runs anywhere = the robust fallback.** OPEN: get BTC judge
  VRAM → decide 26B vs 31B for the Vong-2 Docker. +0.86pp likely NOT worth the 0-risk unless
  BTC ≥40GB is confirmed.
- **RULED OUT (measured no/negative — do NOT re-try):** TIR (level 1), reading-grounding
  (level 2), targeted RAG (level 3), k=5 diverse voting, few-shot, tiered, UD-Q4_K_XL
  quant-swap, Qwen3.5-9B. The ONLY positive lever found is the bigger 31B model (+0.86, marginal).
- **NEXT GOAL: find a NEW accuracy lever** (current levers are exhausted). Candidate untried
  directions: better 26B quantization to recover the Q4 math loss (26B-Q4 quant 82.7% vs
  full-precision 86.7% = −4pp — a real gap, but UD-Q4_K_XL measured slightly negative on a
  small sample, so try OTHER quants); position-bias debiasing on the live path (the 463 pred
  was A/B-heavy, 63%); prompt/CoT refinements; possibly a Gemma-4 size between 26B and 31B if
  one exists. Measure each on the LEADERBOARD (proxies mislead), respecting the 5-trial limit.
- **Dev tooling:** FPT API `fpt-gemma-api` profile (key was `Downloads/ai_gemma.txt`, free $1
  spent; $70 voucher is Japan-region = gemma-3 only). RunPod key `Downloads/runpod987.txt`
  (~$14 left). For a stable 31B GPU run use a ≥40GB card (A6000/A40), n_ctx=8192, source-build
  llama-cpp (CUDACXX=/usr/local/cuda/bin/nvcc, arch 86). Reproducible 31B-Q4 463 pred.csv is
  at `data/q4results/31bq4_public463_pred.csv` (gitignored).
- Full detail: `notes/worklog.md` (2026-06-11→12 entries) + memory note
  `neko-core-current-state-2026-06-11`.

---

## 0. Identity & where you are

- **The real project is Neko Core** at `E:\Sach\Sua\bang_c` (github.com/meiiie/bang_c).
  The shell may open in `E:\Sach\Sua\AI_v1` (Wiii) — that is CONTEXT ONLY. `cd` to bang_c.
- It is the **HackAIthon 2026 Bảng C** entry: an OFFLINE self-contained Docker harness that
  reads `/data/*_test.csv|json`, writes `/output/pred.csv` (`qid,answer`; per-row letters,
  NEVER hard-coded A–D). Scoring on a 2000-question multilingual private test:
  **Accuracy 80 / Time 10 / Idea 10.**
- Allowed models ONLY: Gemma-4 family + Qwen3.5≤9B; embedders BGE-m3 / Qwen-Rerank.
  Runtime: `Gemma-4-26B-A4B QAT Q4_0 GGUF` via llama-cpp-python (offline).

## 1. Rules / SKILL (non-negotiable — these OVERRIDE convenience)

- **karpathy-guidelines**: think before coding (state assumptions, surface trade-offs);
  simplicity (minimum code, no speculative features/abstractions); surgical changes (touch
  only what the task needs, match existing style); goal-driven (every change has a
  verification story).
- **AGENTS.md** + `docs/operations/`: config-first, no god files, no hard-coded answers,
  offline runtime, keep Vietnamese diacritics, never commit secrets/.env/model weights.
- **Anti-overfit (owner's repeated demand)**: every lever MUST generalize to the 2000
  private test. Nothing tuned to the 463 public questions. Negative results are valuable.
- **Honesty**: report real measured numbers; mark anything not-yet-measured as such.
- Notes discipline: investigations in `notes/` (one dated file per topic), durable
  takeaways in `notes/lessons.md`, an append-only journal in `notes/worklog.md`.

## 2. Current state (2026-06-11) — confirmed + built

- **Leaderboard CONFIRMED**: CoT self-consistency = **87.26** vs letter-only baseline 77.11
  (+10.15). Contest default workflow = `self-consistency` (k=1, reasoning_max_tokens=2048).
- **GPU session 2 done** (RunPod A5000 community $0.16/h, ~$0.40 total, pod terminated).
  Measured a 4-variant battery on 150 labeled ViGEText exam MCQs:
  - old Q4_0 k=1 = 89.33% | UD-Q4_K_XL k=1 = 88.00% | +few-shot = 88.67% | tiered = 90.00%
  - All within n=150 noise (±2.6pp). **REJECTED**: quant-swap to UD-Q4_K_XL (measured
    NEGATIVE — keep the current Q4_0); blanket few-shot (flat); blanket tiered (3× slower,
    no real gain). Do NOT re-try these.
- **GROUND-TRUTH PIVOT (most important doc: `notes/public-test-composition-2026-06-11.md`)**:
  analyzed the REAL 463 public test. ViGEText is a BAD proxy. Real composition:
  ~22% reading-comprehension (passage GIVEN → RAG useless), ~25-30% cross-domain
  quantitative (heavy among the 29% that are 10-CHOICE), ~54% factual grab-bag (only a
  ~10-15% VN-legal/admin/Party slice is RAG-addressable). Context never truncates (max
  ~3.4k tok). Owner: test is "nhiều logic" + "toán tổng quát mọi lĩnh vực (Hóa/Lý/Lượng tử)".
- **Verified error-lever analysis** (`notes/error-lever-analysis-2026-06-11.md`, 33-agent
  adversarial workflow): RAG 0 clean wins (gated on reasoning); TIR 2 clean wins (numeric
  only); ~6/16 ViGEText "errors" are DEFECTIVE GOLDS. Build order: TIR → reading-comp → RAG.
- **LEVEL 1 BUILT & COMMITTED (155 tests green)**: Tool-Integrated Reasoning + router.
  - `tool_runtime.py` (offline `python -I -S` sandbox: extract_code + run_python, wall-clock
    timeout, temp cwd, bounded output), `prompting.py` (build_tir_code_prompt /
    build_tir_answer_prompt), `solver.py` (`_solve_tir` k-pass SC-on-setup, degrades to
    reasoning; `_solve_router`: quantitative→TIR else→self_consistency), config
    (tir_samples/tir_exec_timeout_seconds/tir_code_max_tokens; valid_strategies+={tir,router}),
    `tir` + `router` dev workflows. **Default path UNCHANGED** (self-consistency).
- **LEVEL 3 BUILT & COMMITTED (194 tests green, policy PASS, commit 880fe83)**:
  targeted legal-RAG — stdlib BM25 (diacritics kept, df>N/3 cutoff, thread-safe
  failure-memoizing cache), fallible-excerpt prompt, `_solve_rag` degrades to SC on
  any miss/failure. Gates: `has_legal_admin_strong` (≥2 markers, kills polysemy
  false-positives) + math-syntax cue (LaTeX→TIR; real-463 TIR share now 28.1%).
  Corpus: YuITC MIT → 344,713 chunks via `scripts/build_rag_corpus.py` (local copy at
  `data/rag/legal_corpus.jsonl`). `rag_corpus_path` default "" = OFF everywhere.
  18-agent review: 11 findings fixed (index-memory compaction deferred until RAG wins).
  GPU battery READY in `scripts/gpu/` (devsets built+validated locally in
  `data/devsets/`: quant/civics=ViGEText, reading=ViMMRC-1.0, n=150 seeded; arms:
  quant→router, reading→FORCED reading, civics→FORCED rag; paired scoring).
- **LEVEL 2 BUILT & COMMITTED (173 tests green, policy PASS, commit 828f7fc)**:
  reading-comprehension grounding mode — the passage analog of TIR.
  - `prompting.py`: `READING_SYSTEM_PROMPT` + `build_reading_prompt` (quote the exact
    span → vet EVERY option → reject true-but-off-topic / wrong-attribution /
    outside-passage; negation flips to the option WITHOUT support; if no passage is
    supplied, answer from knowledge — kills marker-misroute harm).
  - `solver.py`: `_solve_reading` (SC voting via a `prompt_builder` param on
    `_collect_reasoning_votes`; reuses SC knobs, NO new config); router = quantitative
    →TIR, passage (`kind=="reading"` or `has_long_context`)→reading, else→SC;
    standalone `reading` strategy + dev workflow so GPU measurement can FORCE the mode
    on ViMMRC. CJK context markers added (dense CJK passages miss the length trigger).
  - 9-agent adversarial review: 5 confirmed findings, all fixed (incl. mutation-tested
    `_is_reading` feature branch). **Default path still UNCHANGED.**

## 3. ▶ NEXT TASK — GPU measurement session (GATE ON OWNER: sign-off + RunPod top-up)

Both levers (TIR + reading) are now built and OFF by default. The next step is MEASURE,
not build — do not promote `router` on vibes:

- Re-rent RunPod (~$0.40 last session; balance ~$0.87 — TOP UP first). Stage old Q4_0
  (skopeo from `hacamy12345/neko-core:gemma26b-q4`) + ViGEText
  (`uitnlp/ViGEText_17to23` test, ungated) + ViMMRC (reading proxy).
- Measure `router` vs `self-consistency` PER BUCKET: quantitative on
  ViGEText-math/phys/chem; reading on ViMMRC (use the standalone `reading` workflow to
  force the mode, independent of classifier recall). Also sanity-check the marker
  misroute rate (factual items containing "document"/"article" → reading) — harm is
  neutralized by the no-passage prompt degradation but the routing waste is unmeasured.
- Promote `router` to contest default ONLY if it wins per-bucket with no overall
  regression. NOTE: community pods have old CPUs (no AVX512) → prebuilt llama-cpp wheels
  SIGILL → must source-build (see `notes/lessons.md`). Scripts hygiene: write file → scp
  → `tr -d '\r'` → bash (PowerShell/ssh quoting + sandbox bite otherwise).

## 4. Then: LEVEL 3 (lowest priority, build only after measurement)

- Targeted RAG for the ~10-15% VN-legal/admin/Party factual slice ONLY (fire-safety,
  Cà Mau ID procedure, HCM Thought). Gated, measured first.
  Corpus: vi-wiki parquet (filter <500-char stubs) + VN legal corpus (YuITC MIT 214MB /
  th1nhng0 CC-BY); BGE-m3 GGUF (llama-server --embedding) + BM25 hybrid; Qwen3-Reranker.
  RAG is USELESS for reading-comp (text already given) — only the legal/admin factual slice.

## 5. Credentials (read from files, NEVER commit/echo; pause before spend/publish)

- RunPod API key: `C:\Users\Admin\Downloads\rpa_FIYHE0EN38IUDYZC9TAT6WJ2S2UHZ9P.txt`.
  Balance ~$0.87 — TOP UP before a GPU session.
- Docker Hub: user `hacamy12345`, PAT in `C:\Users\Admin\Downloads\1. Run.txt`. Published
  image `hacamy12345/neko-core:gemma26b-q4`.
- Public test (questions only, NO labels): `C:\Users\Admin\Downloads\public-test_1780368312.json`.
- PAUSE for owner sign-off before: leaderboard submission, GPU/RunPod spend, publishing or
  overwriting the Docker image.

## 6. Guardrails (unchanged)
No hard-coded answers/formulas; no single-language live-path heuristics; keep Vietnamese
diacritics; runtime offline/self-contained; `pred.csv` (`qid,answer`, per-row letters)
always valid; report real numbers, never fabricate; default contest path stays
`self-consistency` until a lever is GPU-measured and proven to generalize.
