# HackAIthon 2026 - Bang C Harness

Status: draft competition harness

This folder is intentionally separate from Wiii Core. It reuses Wiii's
harness mindset, model-routing discipline, and verification loop, but the final
container stays small and reproducible.

## Contest Contract

- Input: `/data/public_test.csv` or `/data/private_test.csv`
- Output: `/output/pred.csv`
- Output columns: `qid,answer`
- Answer format: choice letters such as `A`, `B`, `C`, `D`; the loader also
  supports more choices for local public-test analysis.
- Allowed LLM family from the user's rule screenshot:
  - `Qwen3.5` series with model size <= 9B
  - `Gemma-4` series
- Allowed embedding/rerank family:
  - `BGE-M3`
  - `Qwen-Rerank`

## Current Local NVIDIA Probe

The local Wiii NVIDIA key can list models through
`https://integrate.api.nvidia.com/v1/models`. As of 2026-06-08, the useful
matches include:

- `google/gemma-4-31b-it`
- `baai/bge-m3`

`qwen-rerank` was not visible in the local `/models` response, so rerank remains
an adapter boundary until an available endpoint is confirmed.

## Run Locally

From this folder:

```powershell
$env:NVIDIA_API_KEY = "<set outside git>"
python -m pip install -r requirements.txt
$env:PYTHONPATH = "$PWD/src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5
```

Dry-run smoke test without API:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5 --dry-run
```

Gemma 4 with a second verifier pass:

```powershell
$env:HACKC_LLM_MODEL = "google/gemma-4-31b-it"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --trace-dir traces --limit 5 --verify
```

## Docker

Build:

```powershell
docker build -t wiii-hackaithon-c:dev .
```

Run with a mounted data folder:

```powershell
docker run --rm `
  -e NVIDIA_API_KEY=$env:NVIDIA_API_KEY `
  -v C:\path\to\data:/data `
  -v C:\path\to\output:/output `
  wiii-hackaithon-c:dev
```

## Development Loop

Use web research, subagents, and multi-pass analysis only to improve the method
before packaging. The final runtime path must not depend on live web browsing,
external subagents, Wiii's full backend, or interactive UI state.

Recommended loop:

1. Run baseline on public test.
2. Inspect low-confidence traces.
3. Add one prompt or verifier change at a time.
4. Re-run the same sample and compare answer stability.
5. Keep only changes that improve reproducibility and rule compliance.
