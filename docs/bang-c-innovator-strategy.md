# HackAIthon 2026 Bang C Innovator Strategy

Status: Active draft
Created: 2026-06-08

## Decision

Use Bang C as the primary competition track for the current Wiii team effort.
Keep Bang B/SV5T as a long-term Wiii plugin direction, not the immediate
competition bet.

## Why Bang C Fits Wiii Now

Bang C is a reproducible benchmark task. It rewards a clean inference harness,
model discipline, prompt quality, validation, and output correctness. Those are
closer to Wiii's current strengths than a full social-product MVP.

The submission should not run Wiii full-stack. It should be a small container:

```text
/data/public_test.csv or /data/private_test.csv
  -> loader
  -> solver
  -> verifier/post-process
  -> /output/pred.csv
```

## Model Direction

Prefer `Gemma-4 Series`.

Local NVIDIA model discovery on 2026-06-08 found:

- `google/gemma-4-31b-it`
- `baai/bge-m3`

`google/gemma-4-31b-it` was also smoke-tested through the local NVIDIA key on
one public-test item, including the optional verifier pass. It returned a valid
answer letter and produced `pred.csv`.

`qwen-rerank` was not visible in the local NVIDIA `/v1/models` response at the
time of probing, so rerank should remain an adapter boundary until confirmed.
Use `neko --model-inventory` to re-run this provider check without
changing runtime source code.

## Development Workflow

Use a task-specific harness, inspired by Codex/Odysseus/Wiii:

1. Classify question shape.
2. Select a prompt variant: direct, evidence, elimination, or calculation.
3. Solve with Gemma 4 using a strict one-letter prompt.
4. Normalize answer robustly.
5. Verify or run a small tournament only for risky items.
6. Fall back to deterministic overlap only if the model/API path fails.
7. Trace raw output and strategy in dev mode.
8. Loop on public-test failures and low-confidence traces.
9. Keep the final image free of web crawlers, subagents, UI, and hidden state.

Current strategy modes:

- `direct`: one Gemma call.
- `verify`: one Gemma call plus one verifier call.
- `tournament`: multiple prompt variants, majority vote, optional verifier.
- `auto`: classifier chooses the cheapest safe route.

Subagents and web research are allowed during development for strategy review,
prompt design, and error analysis. They must not be runtime dependencies for the
final contest container.

## Final Container Rules

- Read only `/data/public_test.csv` or `/data/private_test.csv` by default.
- Write only `/output/pred.csv` for contest output.
- Keep output columns exactly `qid,answer`.
- Do not commit API keys, `.env`, local answer files, leaderboard notes, or
  private traces.
- Do not depend on Wiii backend, Docker Compose sidecars, browser automation, or
  local Chrome.
- Keep reproducibility higher priority than clever but brittle prompt chains.

## Current Implementation

Folder:

- repository root (`E:\Sach\Sua\bang_c` locally, `meiiie/bang_c` on GitHub)

Current files:

- `Dockerfile`
- `README.md`
- `docs/submission-readiness.md`
- `src/hackaithon_c/loader.py`
- `src/hackaithon_c/nvidia_client.py`
- `src/hackaithon_c/solver.py`
- `src/hackaithon_c/exporter.py`
- `src/hackaithon_c/submission.py`
- `tests/test_contract.py`

## Review Checklist

- Build image from a clean checkout.
- Run with mounted `/data` and `/output`.
- Confirm `pred.csv` exists and has the same number of rows as input.
- Confirm no duplicate or missing `qid`.
- Confirm every answer is a valid choice letter.
- Run `neko --input <official-test.csv> --check-submission <pred.csv>` before
  manual website upload.
- Run twice and compare outputs.
- Search the repo/image for secrets and answer leakage before submission.
