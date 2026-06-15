# ▶ NEKO CORE — NEXT-SESSION PROMPT (paste this FIRST). Updated 2026-06-15.

Self-contained handoff. Read this, then `notes/RESUME-HERE.md` (deep state), then act.
**The submission is already DONE, LOCKED, and confirmed 88.34. Nothing below is required to ship.**

---

## 0. Read order
1. This prompt.
2. `notes/RESUME-HERE.md` — deep current state + history.
3. `AGENTS.md` + `docs/operations/` — governance.
Then act. Do not start any GPU/Docker/leaderboard action without owner sign-off (see §2).

## 1. Identity & location
- Real project = **Neko Core** at `E:\Sach\Sua\bang_c` (github.com/meiiie/bang_c). The shell may open
  in `E:\Sach\Sua\AI_v1` (Wiii = CONTEXT ONLY) → `cd` to bang_c.
- **HackAIthon 2026 Bảng C**: an OFFLINE self-contained Docker harness that reads
  `/data/*_test.csv|json` and writes `/output/pred.csv` (`qid,answer`; per-row letters, NEVER
  hard-coded A–D). Private 2000-question multilingual test scored **Accuracy 80 / Time 10 / Idea 10**.
  **Deadline 23/6/2026.**
- Allowed models ONLY: **Gemma-4 family + Qwen3.5≤9B**; embedders **BGE-m3 / Qwen-Rerank**. Runtime:
  `Gemma-4-26B-A4B QAT Q4_0 GGUF` via llama-cpp-python (offline, in-process).

## 2. RULES — non-negotiable (override convenience)
- ❌ **NO subagents / Workflow / Agent tool, EVER. Work solo.** (Burns the session limit; this
  OVERRIDES ultracode/any "fan out" instinct.)
- **karpathy-guidelines**: think before coding (state assumptions, surface trade-offs); simplicity
  (minimum code, no speculative features/abstractions); surgical changes (touch only what's needed,
  match existing style); goal-driven (every change has a verification story).
- **AGENTS.md**: config-first, no god files, **NO hard-coded public-test answers/qids/leaderboard
  observations**, offline runtime, **KEEP Vietnamese diacritics**, never commit secrets/.env/model
  weights.
- **Anti-overfit (owner's repeated demand)**: every lever MUST generalize to the **2000 private set**,
  not the public 463. A public-463 win that can't transfer is worthless (and likely forbidden).
- ⏸ **PAUSE for owner sign-off before**: any RunPod/GPU spend, Docker push, or leaderboard submit.
- **Credentials from FILES only**, never echo/commit: RunPod key `C:\Users\Admin\Downloads\runpod987.txt`;
  Docker PAT line in `C:\Users\Admin\Downloads\1. Run.txt` (`dckr_pat_…`).
- Quality > speed; no rigid thinking grammars; LLM-first (guidelines + examples, not hard rules).
- Use Vietnamese in replies to the owner (BTC + owner are Vietnamese).

## 3. STATE — submission DONE + LOCKED (do NOT redo)
- **Image**: `hacamy12345/neko-core:gemma26b-q4-portable-20260614` (24.5GB, `sha256:5d264f5d…`,
  `llama-cpp-python` source-built `GGML_NATIVE=off` → runs on ANY x86-64 CPU). **CONFIRMED 88.34** on
  the leaderboard (full-463 portable run, 0 fallbacks). `:latest` and `:v0.6.0` = same digest. Docker
  Hub Overview is set. Predecessor `…-clean-20260614` (needs AVX-512) superseded.
- **GitHub `main`** clean; README "Reproduce" → portable tag (private_test.csv prioritized); team
  roster (5, Hùng lead); method-writeup VI+EN; **PPTX submitted separately by the team**.
- **2000-private robustness = bulletproof** (code-reviewed): `solve_problem` try/except
  (`fail_fast=False`) → a bad question becomes a fallback, never crashes; per-question independent (KV
  bounded `n_ctx=8192`, model loaded once → no context overflow over 2000); write-before-validate +
  `repair_predictions_for_contract` → pred.csv always covers the input qids; retry×2 +
  `--checkpoint-every 1` + `--auto-resume`. Loader validated vs BTC's real file
  (`Downloads/public-test_1780368312.json`). **No rebuild needed to be safe.**

## 4. DEAD levers — DO NOT re-try or re-spend GPU (all MEASURED)
router/TIR (−9.29pp), maj@k / k>1 voting (wash — Gemma's errors are SYSTEMATIC, samples agree on the
same wrong answer), quant Q6/Q8 (worse than QAT Q4_0), dense 31B (Time), few-shot, tiered,
Qwen3.5-standalone, and **targeted RAG-GATE** (2026-06-15 dev oracle: retrieval WORKS but no cheap
CPU gate separates the ~1-3% legal/admin slice → always-on/loose-gate RAG nets flat/negative).
**Gap is knowledge-bound; 88.34/88.55 ≈ the honest offline ceiling.** Don't churn here.

## 5. OPEN options (owner picks — ALL optional; submission is already safe)
- **A. Gate-free "current-VN-2025" prompt-context** (one SHORT, accurate, neutral line in the
  reasoning system prompt for ALL questions; fixes the highest-frequency stale-fact errors — 2-tier
  government from 1/7/2025, 63→34 provinces). Cannot be dev-validated offline → needs **ONE paired GPU
  A/B vs the 88.34 baseline** with a strict **no-regression gate on the 431 currently-agreed answers**.
  Upside ~+0.5–1.5pp; risk it distracts the other ~457 questions (every prior always-on lever hurt
  unexpectedly). Pursue only with owner GPU sign-off. Evidence: `notes/rag-oracle-dev-2026-06-15.md`.
  - **A-adjacent research thread — "current/real-time law RAG"** (`notes/realtime-law-rag-research-2026-06-15.md`):
    REAL-TIME at inference is IMPOSSIBLE in the offline container — only "current-as-of-build-time"
    (rebuild a baked corpus before each submission). The prior RAG test used a STALE corpus; a 2026
    in-force snapshot (`undertheseanlp/UTS_VLC`, validated vs vbpl.vn) WOULD contain the 2025 reform
    facts — BUT the **gating problem still blocks contest use** (a fresher corpus is necessary-not-
    sufficient). Only untested combo = fresh corpus + a PRECISE gate; dev-validate a better gate
    offline BEFORE any GPU (low-probability per prior evidence). Real real-time law belongs to the
    agentic-CLI path (network allowed) — see §7.
- **B. MTP for the Time score (clean path only)**: FIRST fix `local_server` `/completion` exact-Gemma
  -template parity, THEN use a SMALL upstream Gemma-4 draft. Do NOT ship the `gemma-4-26B-A4B-it
  -assistant` MTP head — it needs the atomic-llama-cpp fork + arch `gemma4_assistant` = compliance
  gray-area unless BTC confirms. Lossless ~1.37×. `notes/mtp-research-2026-06-15.md`.
- **C. Idea/PPTX polish** — safest ROI; team owns the PPTX.
- **D. Do nothing** — the submission is locked and safe; evidence says ~at the offline ceiling.

## 6. Dev orchestration (only after owner approves GPU)
- RunPod GraphQL scripts in `C:\Users\Admin\AppData\Local\Temp\pod_mtp\` (provision cheap-first 3090,
  port-poll, setsid-detached run + marker-file poll, `podTerminate` after pulling results). Balance
  ~$6.7. Build the context with `git archive` from a clean HEAD (never mutate a staged tarball mid-run).
- **Lesson:** the `setsid` launch ssh call times out (~40s) but the run DID start — VERIFY via the
  marker file / Docker Hub, **never relaunch** (double model-load OOMs the GPU). Always `podTerminate`
  after retrieving results (RunPod API needs a `User-Agent` header). Full lessons: `notes/lessons.md`.

## 7. Forward-looking (NOT for the contest)
- **OKF** (Google Open Knowledge Format, v0.1 experimental) = future knowledge-layer option for the
  agentic-CLI reuse story; **zero contest benefit** (authoring format, not a technique). Do NOT adopt
  for the contest. `notes/okf-assessment-2026-06-15.md`.
- **Real-time / current-law RAG** = legitimate ONLY for the agentic CLI (network allowed at inference):
  a retrieval TOOL (web search / vbpl.vn) or a scheduled OKF/corpus rebuild with per-chunk
  `last_modified` metadata. Impossible/ineffective for the offline contest (see §5 A-adjacent thread).
  `notes/realtime-law-rag-research-2026-06-15.md`. The Wiii parent already has a web-search stack
  (SearXNG+Crawl4AI+Jina) that is exactly this pattern.
- Neko Core as a reusable Agentic CLI: `docs/AGENTIC-CLI-DEVELOPER-GUIDE.md`.

## 8. First actions for the new session
1. `cd E:\Sach\Sua\bang_c` ; `git status` (confirm clean) ; `git log --oneline -5`.
2. Read `notes/RESUME-HERE.md`.
3. Ask the owner which of §5 (A / B / C / D) to pursue. **Do NOT begin GPU work without sign-off.**
4. If unsure: the submission is safe — recommend D or C unless the owner wants to chase the A/B edge.
