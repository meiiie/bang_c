# 2026-06-26 — Round-2 submission contract fix (CRITICAL)

**Trigger:** BTC released the detailed *Submission Guideline* (Google Doc) for the Round-2 final
submission. It defines a contract that the shipped image (`qwen3-4b-selfconsist-20260618`) did **not**
implement — submitting as-is would very likely score 0 on the automated grader.

## Gap found (BTC doc vs shipped image)

| BTC Submission Guideline | Shipped image (v0.7.2) | Severity |
|---|---|---|
| Input: `/code/private_test.json` (JSON list) | reads `/data/*_test.csv` | 🔴 wrong path/format |
| Output: `submission.csv` (`qid,answer`) | writes `/output/pred.csv` | 🔴 wrong filename |
| Output: `submission_time.csv` (`qid,answer,time`, per-sample) | not produced | 🔴 missing → no Time score |
| Base image **CUDA 12.2** (mandated, matches judge driver) | CUDA **12.8** (runpod/pytorch) | 🔴 GPU init fails on 12.2 driver |
| Entry `predict.py` + `inference.sh` (`CMD ["bash","inference.sh"]`) | `python -m hackaithon_c.run` | 🟡 convention |

**Deadline:** image pushed to DockerHub before **23:59 (UTC+7) 2026-06-27**.

Evidence the CUDA gap is real: the dev machine (GTX 1650, driver 560.94 = CUDA 12.6 max) **cannot run**
the 12.8 image — so a 12.2-era judge driver would also fail it.

## Schema (confirmed from BTC public test `public-test_1780368312.json`, 463 items)

JSON **array**; each item `{"qid":"test_0001","question":"…","choices":["…","…","…","…"]}`. No answer
field. The harness `loader._load_json` already parses this exact shape (flexible qid/question/choices keys).

## Fix (reuses the validated engine; only I/O + timing added)

- **`predict.py`** — reads `/code/private_test.json` (fallback `/data/*_test.{json,csv}`), solves ONE
  item at a time with `solve_problem` (workflow `self-consistency` = k=1 CoT, same config overlay),
  times each item with `time.perf_counter()`, runs `repair_predictions_for_contract` (every qid → valid
  letter), and writes `submission.csv` + `submission_time.csv` to `/code` and `/output`. Per-item
  try/except so one bad item can't zero the run. `NEKO_DRY_RUN=1` solves via heuristic (no model/GPU).
- **`inference.sh`** — `cd /code && exec python3 predict.py "$@"`. (`CMD ["bash","inference.sh"]`.)
- **`Dockerfile.qwen-submission`** — `nvidia/cuda:12.2.2-devel-ubuntu22.04` + Python 3.11 (deadsnakes) +
  source-built `llama-cpp-python` (CUDA 12.2, `GGML_NATIVE=off`, multi-arch sm_70..90 + compute_60 PTX
  floor) + Qwen3-4B-Instruct-2507 Q5_K_M baked. `WORKDIR /code`. The engine, model, prompts, and config
  are untouched, so accuracy parity with the validated 83.59 path is preserved.

## Verified so far

- **Dry-run on the 463-item public test (no model):** loads 463, writes `submission.csv` (464 lines,
  0 empty answers) + `submission_time.csv` (464 lines, time column numeric) — format matches the BTC
  example byte-for-byte. I/O wiring PASS.
- Image build (CUDA 12.2) + GPU smoke + DockerHub push: in progress (this session).

## Image (new)

`hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626` — built from `Dockerfile.qwen-submission`.
The old `qwen3-4b-selfconsist-20260618` is the OLD (non-compliant) contract — do NOT submit it for R2.
