# Operating Loop

Claude Code is strongest when it has a closed loop. Give it a task, a boundary,
and a check it can run.

## Default Loop

1. Explore
   - Read `AGENTS.md`, the relevant note, and the smallest code area.
   - Use plan mode for anything touching runtime, Docker, model paths, or scoring.
2. Plan
   - State assumptions.
   - Name files likely to change.
   - Name the verification command before editing.
3. Implement
   - Make the smallest change that advances the task.
   - Keep data-dependent knobs in `configs/default.json` or explicit config.
   - Keep pure speed levers in provider/runtime code, not solver logic.
4. Verify
   - Run the smallest targeted check first.
   - Then run broader checks when the blast radius warrants it.
5. Record
   - Write durable experiment outcomes in `notes/`.
   - Put reusable lessons in `notes/lessons.md`.
   - Do not commit generated outputs, traces, model weights, or secrets.

## Neko Core Verification Ladder

`.\neko-core.ps1` is the canonical human-facing entrypoint from `AGENTS.md`.
`python -m hackaithon_c.run` is the equivalent developer module entrypoint when
`PYTHONPATH` is set. Prefer the wrapper in user-facing docs and the module form
for fast local checks.

Start narrow:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m compileall -q src
python -m unittest tests.test_throughput -v
```

Then broaden:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests -v
.\neko-core.ps1 --doctor
python -m hackaithon_c.run --policy
```

For contract checks:

```powershell
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output-dryrun --trace-dir traces-dryrun --dry-run
.\neko-core.ps1 --check-submission output-dryrun\pred.csv --input "C:\Users\Admin\Downloads\public-test_1780368312.json"
```

`--policy` and `--check-submission` are supplemental repo checks beyond the
minimal command list in `AGENTS.md`; keep using them for runtime-boundary and
submission-contract work.

For model/GPU work, run only after owner sign-off:

```powershell
.\scripts\verify.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json"
.\scripts\evaluate.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json" -Limit 10
```

For non-dry-run workflows marked `phase=development`, or direct CLI selection
of development-only strategies, the harness requires an explicit experiment
opt-in: `--allow-development-workflow` or
`HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1`. Do not add that flag to the final Docker
entrypoint or routine contest runtime path.

## Current MTP Workstream

Use Claude Code for MTP as an executor/reviewer, not as the source of truth.

The current MTP state is: CUDA offload has been confirmed, and the active
blocker moved to `llama.cpp` tooling/measurement. Do not route new work through
`llama-cli` one-shot benchmarking; current master behaves like an interactive
REPL in the tested path.

The next GPU task is:

1. read `notes/session-2026-06-12.md` and `notes/mtp-direction-2026-06-12.md`;
2. run `OWNER_SIGNOFF=1 bash scripts/gpu/run_mtp_server.sh` on RunPod after
   owner sign-off;
3. pull `/workspace/mtp_server_logs/*` and `/workspace/SRV_DONE` before
   terminating;
4. record measured tok/s, acceptance, GPU, VRAM, and llama.cpp commit;
5. run `python scripts/assess_experiment_results.py --mtp-summary
   /workspace/mtp_server_logs/summary.txt --min-mtp-speedup 1.4`;
6. integrate through `local_server` or `local_llamacpp` only after measurement
   and owner review.

Do not promote MTP from upstream claims alone. It needs local GPU logs, speed
numbers, and answer-equivalence checks. It must remain an offline, self-contained
runtime/provider acceleration: the final Docker still reads `/data`, writes
`/output/pred.csv`, keeps the current Gemma-4 local runtime direction unless the
owner explicitly changes it, and does not depend on web services, RunPod,
notebooks, hidden state, or Claude Code.
