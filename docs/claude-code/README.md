# Claude Code Playbook for Neko Core

Status: active
Last updated: 2026-06-13

This folder is the team operating manual for using Claude Code effectively on
Neko Core. It adapts the official Claude Code guidance to this repository's
contest constraints: offline final Docker, config-first runtime profiles,
measured accuracy/time tradeoffs, and no public-test or leaderboard hacks.

## Read Order

1. `CLAUDE.md` at the repo root imports `AGENTS.md` so Claude Code sees the
   same non-negotiable project rules as Codex.
2. `setup-and-context.md` explains startup, memory, permissions, and session
   hygiene.
3. `operating-loop.md` gives the day-to-day loop: explore, plan, implement,
   verify, record.
4. `prompt-patterns.md` provides copy-ready prompts for this project.
5. `subagents-skills-hooks.md` explains when to use Claude Code subagents,
   skills, hooks, and non-interactive mode.
6. `dynamic-workflows.md` explains when to use Claude Code's dynamic workflows
   for multi-agent harnesses and when they are overkill.

## Current Local Claude Code

Observed in this workspace:

```text
Claude Code 2.1.177
cwd: E:\Sach\Sua\bang_c
model in terminal: Opus 4.8, effort ultracode
```

Project default:

- interactive Claude Code: keep Opus 4.8 and `/effort ultracode`;
- non-interactive `claude -p`: use `--model opus --effort max`;
- if Claude Code exposes a literal `ultracode` CLI flag in a future version,
  prefer that over `max`.

The observed terminal session is currently in bypass-permissions mode. Treat
that as an exception for a trusted workspace, not the default recommendation.
Even there, follow the canonical owner sign-off list in
`setup-and-context.md`.

## Sources Checked

- Claude Code overview: https://code.claude.com/docs/en/overview
- Claude Code best practices: https://code.claude.com/docs/en/best-practices
- Claude Code memory / CLAUDE.md: https://code.claude.com/docs/en/memory
- Claude Code permissions: https://code.claude.com/docs/en/permissions
- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code skills: https://code.claude.com/docs/en/skills
- Claude Code hooks: https://code.claude.com/docs/en/hooks-guide
- Claude Code CLI reference: https://code.claude.com/docs/en/cli-reference
- Claude dynamic workflows:
  https://claude.com/blog/a-harness-for-every-task-dynamic-workflows-in-claude-code

## Team Rule

Claude Code is allowed for development, research, review, and automation. It is
not part of the final scoring path. Anything learned by Claude Code must land as
repo code, config, tests, prompts, docs, or notes.
