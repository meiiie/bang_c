# ▶ RESUME HERE

Single entry point for the next session/agent. Read this first, then `EXECUTOR-PLAYBOOK.md`.

## State as of 2026-06-10 (all model-independent work done, verified)

| Phase | Status | Evidence |
|---|---|---|
| P0 safety net | ✅ done | 24-item gold suite, 6+ scripts (Latin/CJK/Cyrillic/Arabic-RTL/Thai), 0 crash |
| P1 reasoning + self-consistency + calibration | ✅ **code** done | `calibration.py`, `self_consistency` strategy; **not yet measured/cut over** |
| P2 routing (calc over-trigger + multilingual negation) | ✅ done | gold routing 0 errors; live path improved |
| P3 cross-model challenger + tiering | ✅ **code** done | `solve_with_challenge`; gated off (challenger=None) |
| P4 modular refactor | ⏸ deferred | would churn legacy code slated for deletion |
| Method write-up (DoD #6) | ✅ draft | `docs/method-writeup.md` |

**104 unit tests green. Contest path untouched → zero regression risk.** Full detail in
`notes/worklog.md`.

## ✅ REAL-MODEL TEST DONE (2026-06-10, RunPod A40 + Gemma-4-26B) — see worklog

Tested on the actual contest model. Headline: **CoT reasoning (k=1, max_tokens=2048) beats the
baseline on the 5 gold (5/5 vs 4/5)** and changed 91/463 answers (concentrated on calculation,
38%). Found+fixed a real bug (max_tokens=512 truncated CoT). Sovereignty probe PASS (model is
Vietnam-aligned, no mitigation needed). Packaged candidate image
`hacamy12345/neko-core:gemma26b-q4-cot-20260610` (CoT default). Pod terminated (~$0.72 spent).

**The verdict is NOT final** — the 91 differing answers need the leaderboard (only 5 gold
labels held locally). NEXT (owner): **submit `E:\Sach\Sua\_tmp\neko-core-runpod-a40-20260610\
pred-cot-463.csv` to the leaderboard** → compare to 85.53. If CoT wins, lock the cutover
(contest workflow → reasoning, samples=1) and that image is the final submission.

## ✅ Unblock → then run, in order

1. Provide a model (NVIDIA path is easiest — needs no build, only `requests`):
   ```powershell
   setx NVIDIA_API_KEY "<key>"     # then open a NEW terminal   (dev: Gemma-4-31b)
   ```
   Local GGUF path needs a working `llama-cpp-python`. NOTE (verified 2026-06-10): there is
   **no prebuilt wheel for Python 3.13** on this machine, so the local path requires either
   Python 3.11/3.12 (which have prebuilt wheels) or a C++/CMake build toolchain, plus the
   GGUF at `C:\models\gemma-4-26B_q4_0-it.gguf` and `pip install -r requirements-local.txt`.
2. Measure P1 (reasoning vs current) on a sample:
   ```powershell
   cd E:\Sach\Sua\bang_c
   .\scripts\evaluate.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" `
     -Workflows contest-strict,self-consistency -Limit 40
   ```
   Compare answer stability + whether agreement-based confidence separates right/wrong
   better than the old hard-coded confidence. Record real numbers in `docs/method-writeup.md`
   and `notes/worklog.md`.
3. If reasoning wins → tune `self_consistency_samples` / `reasoning_max_tokens`, then make
   it the contest path (P1 exit). Then harden `normalize_answer` against the *actual* CoT
   formats the model emits (don't guess formats blind).
4. **PAUSE for human sign-off** before deleting the overfit adjudicators (P2; public-dip
   risk) and before any leaderboard submission.
5. Then P3 wiring (build a 2nd provider client, `solve_with_challenge`) → P4 refactor →
   rebuild + validate the Gemma Docker image → record the leaderboard number.

## Guardrails (unchanged)
No hard-coded answers/formulas; no single-language live-path heuristics; keep Vietnamese
diacritics; runtime container offline/self-contained; `pred.csv` (`qid,answer`, per-row
letters) always valid; report real numbers, never fabricate.
