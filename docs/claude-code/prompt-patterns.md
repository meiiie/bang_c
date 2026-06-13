# Prompt Patterns

Use prompts that name the scope, the constraints, and the verification command.

## Codebase Research

```text
Use plan mode. Read AGENTS.md, docs/harness-architecture.md, and the files
under src/hackaithon_c that own <topic>. Do not edit files. Return:
1. the current flow,
2. extension points,
3. risks,
4. the smallest safe next change,
5. verification commands.
```

## Surgical Patch

```text
Implement <specific behavior>. Touch only <files/modules>. Follow AGENTS.md:
config-first, no public-test hacks, no hidden provider branches. Before editing,
state the verification command. After editing, run it and report exact output.
```

## MTP Runtime Work

```text
Read notes/session-2026-06-12.md, notes/mtp-direction-2026-06-12.md, and
notes/runpod-setup-gotchas.md.
Do not change solver prompts or accuracy logic. MTP is a runtime/provider speed
lever. Inspect scripts/gpu/run_mtp_server.sh for server startup, CUDA offload
logging, full llama.cpp load logs, KV f16, draft acceptance, and
baseline-vs-MTP measurements. Suggest the smallest patch and how to verify it.
```

## Review

```text
Take a code-review stance. Findings first, ordered by severity, with file and
line references. Focus on contest contract regressions, provider/runtime
boundary leaks, hard-coded public-test assumptions, missing verification, and
secret/output/model-weight exposure. If no issues, say so and name residual
risk.
```

## Trace Investigation

```text
Inspect <trace-dir>. Do not run model inference. Summarize fallback reasons,
strategy distribution, invalid outputs, changed answers versus <baseline>, and
the smallest next experiment. Report measured facts separately from hypotheses.
```

## Commit Prep

```text
Review the git diff. Separate my changes from unrelated scratch files. Do not
stage generated outputs, traces, secrets, GGUFs, or private answer files. Create
a concise commit message that names the behavior and verification run.
```

## When Claude Should Ask First

Use the canonical owner sign-off list in `setup-and-context.md`. In prompts,
tell Claude to pause before:

- spending RunPod/GPU credits;
- publishing Docker images;
- uploading leaderboard files;
- changing the default contest workflow or model/runtime direction;
- using model artifacts outside the contest-allowed families;
- exposing, printing, moving, or committing API keys and other secrets;
- committing generated outputs, trace logs, public/private answer files, or
  model weights;
- deleting user-created outputs or notes;
- force-push, reset, or destructive git operations.
