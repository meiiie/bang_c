# Setup and Context

## Start From The Repo Root

```powershell
cd E:\Sach\Sua\bang_c
claude
```

Use a named session for workstreams that will continue later:

```powershell
claude --name neko-mtp-runtime
```

For a read-only exploration session:

```powershell
claude --permission-mode plan --name neko-explore
```

For a one-off scripted query:

```powershell
claude -p --model opus --effort max "Read AGENTS.md and summarize the current verification commands."
```

Interactive sessions should use Opus 4.8 with `/effort ultracode`. The current
CLI accepts `--effort max` as its highest non-interactive effort; treat that as
the scripted equivalent unless a future Claude Code release exposes
`ultracode` as a CLI effort value.

## Memory Files

Claude Code reads `CLAUDE.md`, not `AGENTS.md`, so the root `CLAUDE.md` imports
`AGENTS.md`. Keep `CLAUDE.md` short. It should contain rules that apply to every
Claude Code session, not long tutorials.

Use `CLAUDE.local.md` for personal notes and keep it out of git. This repo's
`.gitignore` excludes it.

Good `CLAUDE.md` content:

- project-specific build and test commands;
- non-obvious runtime constraints;
- files that are safe or unsafe to edit;
- sign-off requirements for external actions.

Bad `CLAUDE.md` content:

- full API documentation;
- stale experiment logs;
- generic advice such as "write clean code";
- long file-by-file summaries Claude can discover by reading the repo.

## Permissions

Recommended modes:

- `plan`: for research, codebase reading, architecture review, and contest-rule
  interpretation.
- `default`: for ordinary edits where you want approval prompts.
- `acceptEdits`: for trusted narrow doc or test changes.
- `bypassPermissions`: exception-only. Use it only in a trusted workspace when
  the task is clear, the write scope is narrow, and recovery through git is
  straightforward.

Canonical owner sign-off list. Even in bypass mode, require explicit owner
sign-off before:

- RunPod or GPU spend;
- Docker Hub push or overwrite;
- leaderboard upload;
- changing the default contest workflow or model/runtime direction;
- using model artifacts outside the contest-allowed families;
- exposing, printing, moving, or committing API keys and other secrets;
- committing generated outputs, trace logs, public/private answer files, or
  model weights;
- deleting user-created outputs or notes;
- force-push, reset, or destructive git operations.

## Context Hygiene

Use `/clear` between unrelated tasks. Use `/compact` when a long session must
continue but the context is becoming noisy. When compacting, preserve:

- modified file list;
- commands run and results;
- open blockers;
- measured numbers;
- next verification step.

Use `claude --continue` for the latest session and `claude --resume` when you
need to choose a named session.
