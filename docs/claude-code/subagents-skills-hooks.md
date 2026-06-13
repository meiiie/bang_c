# Subagents, Skills, Hooks, And Automation

## Subagents

Use subagents when the side task would consume lots of context: broad search,
log reading, alternative root-cause analysis, or fresh code review.

Good Neko Core subagent jobs:

- "Inspect MTP offload logs and list CUDA failure signatures."
- "Review the Docker runtime path for `/data -> /output/pred.csv` regressions."
- "Read contest docs and summarize constraints; do not edit code."
- "Review this patch for hidden public-test assumptions."

Avoid subagents for the immediate blocking task when the main session cannot
proceed without their answer. Keep implementation work in one place unless the
write sets are clearly disjoint.

## Skills

Use skills for repeatable procedures that are too long for `CLAUDE.md`.

Candidate project skills:

- `neko-runtime-review`: provider/profile/Docker boundary review.
- `neko-runpod-measure`: after explicit owner sign-off, RunPod launch,
  health-check, pull logs, terminate.
- `neko-contest-contract`: `/data` input, `/output/pred.csv`, per-row letters.
- `neko-mtp-bench`: CUDA offload smoke and baseline vs draft-MTP logging.

Keep skill bodies short and put long references in supporting files. A skill
should tell Claude when to use it, what to read, what not to touch, and what
verification proves completion.

## Hooks

Hooks are for deterministic checks that must happen, not advice. Use them
sparingly because a bad hook can block normal work.

Useful hooks for this repo:

- block writes to `*.gguf`, `*.safetensors`, `.env`, and known key files;
- warn before edits under `Dockerfile*` unless the prompt mentions Docker;
- run formatting or lightweight tests after edits to selected source files;
- stop hook that reminds Claude to run `--policy` after runtime boundary edits.

Do not rely on `CLAUDE.md` to enforce safety. If an action must be impossible,
use permissions or a hook.

## Non-Interactive Mode

Use `claude -p` for scripted read-only or bounded analysis:

```powershell
git diff -- src configs docs | claude -p --model opus --effort max "Review this diff for contest contract regressions. Findings only."
```

For machine-readable output:

```powershell
claude -p --model opus --effort max "List changed files by risk category" --output-format json
```

For minimal startup with explicit context:

```powershell
claude --bare -p --model opus --effort max "Read @AGENTS.md and summarize the verification commands."
```

Do not use non-interactive mode for actions that can spend money, publish, or
delete artifacts unless the command has a deterministic guard outside Claude.

## Parallel Sessions

Use separate sessions or worktrees for independent experiments. Name them by
workstream:

```powershell
claude --model opus --name neko-mtp-bench
claude --model opus --worktree mtp-server-packaging --name neko-mtp-server
```

After the session opens, set `/effort ultracode`.

Before merging results, run:

```powershell
git status --short --branch
python -m unittest discover -s tests -v
python -m hackaithon_c.run --policy
```
