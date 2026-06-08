# Neko Core

Status: draft competition harness

Neko Core is a draft competition harness for HackAIthon 2026 Bang C. This
folder is intentionally separate from Wiii Core. It reuses Wiii's harness
mindset, model-routing discipline, and verification loop, but the final
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

## Config-First Harness

Runtime behavior is configured through `configs/default.json`:

- input file candidates;
- output filename and columns;
- default model and NVIDIA base URL;
- retry/timeout policy;
- multilingual profiling markers;
- classifier thresholds;
- harness rubric weights.

Use `--config path\to\config.json` to run a different profile. The goal is to
adapt to private-test variation without editing source code.

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

One-command local install:

```powershell
.\scripts\bootstrap.ps1
.\neko-core.ps1 --help
.\neko-core.ps1 --doctor
.\neko-core.ps1 --capabilities
.\neko-core.ps1 --agents
.\neko-core.ps1 --tools
.\neko-core.ps1 --commands
.\neko-core.ps1 --policy
.\neko-core.ps1 --model-inventory
.\neko-core.ps1 --list-workflows
.\neko-core.ps1 --init
```

`bootstrap.ps1` creates `.venv`, installs the local editable package, and runs
fast checks for `--version`, `--doctor`, `--policy`, and `--list-workflows`.
Use `.\scripts\bootstrap.ps1 -SkipChecks` only when you need installation
without validation.

Or install manually:

```powershell
$env:NVIDIA_API_KEY = "<set outside git>"
python -m pip install -r requirements.txt
$env:PYTHONPATH = "$PWD/src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5
```

After bootstrap, use the local CLI shim:

```powershell
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5
```

`.\bang-c.ps1` remains as a compatibility alias.

CLI fast paths inspired by Claude Code:

- `--version`: identity check without running inference.
- `--banner`: ASCII brand preview.
- `--doctor`: local environment and contest-contract diagnostics.
- `--init`: create `.neko-core/config.json` for project-local workflow/model
  tuning without editing source files.
- `--capabilities`: explicit runtime/development capability registry.
- `--agents`: named harness role registry for runner, classifier, solver,
  verifier, reviewer, resolver, session inspection, and model inventory.
- `--agent <name>`: inspect one role's tools, reads, writes, and handoff
  boundary, for example `--agent task-resolver`.
- `--tools`: tool contract registry with runtime/development phase, status,
  permission class, inputs, outputs, and guardrails.
- `--tool <name>`: inspect one tool contract, for example `--tool web-research`
  or `--tool exporter`.
- `--commands`: command registry with phase, category, example, and guardrail
  for each CLI or script surface.
- `--command <name>`: inspect one command, for example `--command run` or
  `--command trace-review`.
- `--policy`: audit runtime/development boundaries across registry surfaces.
  The solve path also enforces this gate before loading input or model state.
- `--model-inventory`: probe NVIDIA `/models` and filter models by Bang C
  allowed LLM and embedding/rerank families. Combine with `--run-dir` to save
  `model-inventory.txt` before model experiments.
- `--list-workflows`: named runtime/development workflow registry.

Configured workflow examples:

```powershell
.\neko-core.ps1 --workflow quick-dry-run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5
.\neko-core.ps1 --workflow verify-all --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5
.\neko-core.ps1 --workflow quick-dry-run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --run-dir run-smoke --limit 5
```

`--run-dir` is a development session path. It writes `output/pred.csv`,
`traces/`, `run-report.md`, `review-tasks.md`, `review-tasks.json`, and
`events.jsonl` together so experiments can be reviewed without remembering
separate output and trace paths.

Session inspection, inspired by Claude Code's `/resume` and `/session`
surfaces:

```powershell
.\neko-core.ps1 --list-runs --runs-root .
.\neko-core.ps1 --session run-smoke
.\neko-core.ps1 --events run-smoke
```

These commands only read local artifacts. They show workflow, model, contract
status, trace review status, review-task count, and the next review/resolve
commands for a run folder. `--events` renders the run timeline: session start,
per-qid prediction completion, trace writing, review, and session completion.

Verification report inspired by Claude Code's verification-agent pattern:

```powershell
.\scripts\verify.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json"
.\scripts\verify.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" -Docker
```

The report prints command/output/result blocks and ends with `VERDICT: PASS`,
`VERDICT: FAIL`, or `VERDICT: PARTIAL`.

Workflow eval comparison:

```powershell
.\scripts\evaluate.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" -Limit 10
.\scripts\evaluate.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" -Workflows quick-dry-run,contest-auto -Limit 10 -Repeat 1
```

The eval script runs selected workflows as `--run-dir` sessions, compares
`pred.csv` stability, runs trace review, compares each run to the first run,
and writes per-run artifacts under `eval-runs/`, including `run-report.md`,
`review.txt`, and `compare-to-first.txt`. Each eval directory also includes
`eval-summary.json` and `eval-report.md` with a selected candidate for
machine-readable and human-readable run history.

Trace review:

```powershell
.\neko-core.ps1 --review-trace traces-verify
.\neko-core.ps1 --review-tasks traces-verify --run-dir run-review-tasks
.\scripts\resolve-tasks.ps1 -TaskPath run-review-tasks\review-tasks.json -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" -Workflow verify-all
.\neko-core.ps1 --compare-traces traces-before traces-after
.\neko-core.ps1 --compare-traces traces-before traces-after --compare-qid test_0001
```

The reviewer is development-only. It reads `run-summary.json` plus
`predictions.trace.jsonl`, then reports low confidence, fallback paths, trace
warnings, missing roles, and blocked steps without touching `pred.csv`.
Trace comparison is also development-only; it compares manifest hashes,
prediction counts, changed answers, confidence drift, and fallback drift between
two runs.
Review tasks convert non-info findings into an action queue that another agent
or team member can work through without changing the contest artifact.
`scripts/resolve-tasks.ps1` reads that queue, reruns qid-scoped tasks with a
selected workflow, and writes `task-resolution-report.md`,
`task-resolution.json`, command output, and a scoped trace comparison when the
source run has a sibling `traces/` directory.

Dry-run smoke test without API:

```powershell
$env:PYTHONPATH = "$PWD/src"
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --limit 5 --dry-run
```

Gemma 4 with a second verifier pass:

```powershell
$env:HACKC_LLM_MODEL = "google/gemma-4-31b-it"
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --trace-dir traces --limit 5 --strategy verify
```

Auto strategy with selective tournament:

```powershell
$env:HACKC_LLM_MODEL = "google/gemma-4-31b-it"
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output --trace-dir traces --limit 10 --strategy auto
```

Strategies:

- `direct`: one model call using the classifier-selected prompt variant.
- `verify`: direct call plus verifier call for every item.
- `tournament`: multiple prompt variants, majority vote, then optional verifier.
- `auto`: classifier decides when to verify or tournament. This is the default.

If a model returns explanation instead of a letter, the harness can run one
configured repair pass before falling back to heuristic overlap. This is
controlled by `runtime.repair_invalid_output` in `configs/default.json`.

Trace mode writes:

- `predictions.trace.jsonl`: raw model answer, normalized answer, strategy,
  question kind, confidence, fallback reason, and structured agent steps such
  as `classifier`, `solver`, `repair`, `verifier`, or `synthesizer`.
- `run-summary.json`: contract validation, strategy counts, question-kind
  counts, fallback count, average confidence, harness score.
- `run-manifest.json`: reproducibility metadata including config/input hashes,
  selected workflow, strategy, model, output path, trace path, and CLI args.

## Docker

Build:

```powershell
docker build -t neko-core:dev .
```

Run with a mounted data folder:

```powershell
docker run --rm `
  -e NVIDIA_API_KEY=$env:NVIDIA_API_KEY `
  -v C:\path\to\data:/data `
  -v C:\path\to\output:/output `
  neko-core:dev
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

## Architecture Notes

The harness borrows product discipline from Wiii, Codex, Odysseus, and Goose:

- typed input/output contracts;
- provider/model state configured outside source code;
- small workflow modules instead of one prompt blob;
- explicit trace/eval artifacts for development;
- final container path kept independent of UI, browser, database, and web tools.

Detailed architecture and scoring notes:

- `docs/harness-architecture.md`
- `docs/evaluation-rubric.md`
