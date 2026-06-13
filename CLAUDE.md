@AGENTS.md

## Claude Code Notes

- Read `docs/claude-code/README.md` before long or multi-step sessions.
- Preferred local model/effort for this project: Opus 4.8 with ultracode in
  interactive sessions; for `claude -p`, use `--model opus --effort max`.
- Use plan mode for multi-file runtime, Docker, RunPod, model, or contest-submission work.
- Keep MTP and other speed work at the runtime/provider layer; do not branch solver logic for a pure speed lever.
- Do not spend RunPod/GPU credits, publish Docker images, submit leaderboard files, or expose secrets without explicit owner sign-off in the current session.
- After any meaningful change, run the smallest relevant check first, then broaden to the repo verification commands from `AGENTS.md`.
