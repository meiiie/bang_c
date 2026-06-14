# MTP image packaging session — 2026-06-14 (errors, fixes, lessons)

Status: in progress. Goal = build + push the clean **Gemma-MTP** Docker image (owner chose MTP
direction; renting RunPod is accepted). The image is built fresh from the cleaned HEAD, so it
carries no public-463 hard-codes in any layer, and adds the ~1.37x MTP Time lever (safe fallback
to in-process `local_llamacpp`).

Approach: **Phase A** (SSH-monitored) proves the MTP runtime end-to-end on a pod — build
`llama-server` (pinned ref + `ui.cpp` fix), download both GGUFs, run the real
`docker/neko-entrypoint.sh` MTP path to a valid `/output/pred.csv`. **Phase B** = package + push
with Kaniko (monitored setup → blind executor → verify via Docker Hub). Orchestration lives in
`C:\Users\Admin\AppData\Local\Temp\pod_mtp\` (prov_mtp / phase_a / phase_a_launch / kaniko_build /
phase_b_launch / poll_a / poll_hub). Build context = `Dockerfile.gemma-mtp.kaniko` +
`scripts/docker_fetch_models.py` (new, committed-worthy) + the runtime tree.

## What is SOUND (so the noise below is kept in perspective)
- The harness, the BuildKit/Kaniko Dockerfiles, the `pred.csv` contract — all fine. 227 tests green.
- The actual build is good: `llama-server` compiles at pinned llama.cpp `597b6672` with the
  `ui.cpp` zero-asset patch, `--help` shows `draft-mtp`, all `libggml*.so` (incl. CUDA) build.
- Both GGUFs download anonymously (gated=False): main 14.44 GB, MTP draft only 0.46 GB → no HF
  token needed; final image ≈ same size as the local image.
- **Every failure below was an orchestration/script bug on my side, not a product defect.**

## Incident log (chronological) — error → root cause → fix
1. **Corrupt build context (pod 1).** Re-tarred the context while the launcher was scp-ing it (warm
   pod, SSH up in ~0s). → Don't mutate a staged artifact once a launch is in flight; stage, then go.
2. **Kaniko killed the pod's sshd (pod 1).** `/kaniko/executor` rewrites `/` from the base image →
   wiped sshd host keys/libs → `Connection reset`, build unmonitorable. → Split into monitored
   pre-flight + blind executor; verify via Docker Hub, not SSH. Terminated pod (no tag pushed).
3. **`tar` ownership (pod 2).** Windows git-bash tarball stamps Windows uid/gid; GNU tar as root
   `chown`s to them → `Invalid argument`, exit 2. → extract with `tar --no-same-owner`.
4. **`pkill -f` self-kill.** `ssh host 'pkill -9 -f "git clone"'` matched the ssh command line
   itself (it contains "git clone") → killed the session (exit 255). → kill by name (`pkill -9 git`).
5. **Slow/flaky GitHub git-protocol (pod 2).** Full `git clone` (missing `--depth 1`) ran at
   ~93 KB/s; shallow fetch died `early EOF / invalid index-pack`. HF was fast on the same pod. →
   download llama.cpp as an HTTPS tarball (`codeload .../archive/<sha>.tar.gz`). Terminated pod.
6. **SSH channel hangs (pod 2/3).** Trivial commands occasionally hung 120s. → `ServerAliveInterval`
   on ssh; merged `tr`+launch into one detached call so a hang can't crash the launcher.
7. **Poll false-positive.** Monitor matched "A_DONE" inside an ssh-timeout error string (which echoes
   the polled `ls .../A_DONE` command). → guard `"(ssh err" not in output` before the marker test.
8. **`NO_DRAFT_MTP` (pod 3) — the tricky one.** Two layered causes: (a) the `--help` capability check
   ran before `LD_LIBRARY_PATH` was set, so the thin `llama-server` couldn't load `libggml*.so`;
   (b) even after fixing the lib path, `set -o pipefail` + `--help | grep -q draft-mtp` reported
   failure via SIGPIPE (grep -q closes the pipe on first match → `--help` gets SIGPIPE 141 →
   pipefail fails the pipe) DESPITE the match. Manual runs passed because interactive shells have no
   pipefail. → set the lib path before the check, and grep a captured file instead of a pipe.

## Files changed this session (working tree, not yet committed)
- `Dockerfile.gemma-mtp.kaniko` (new) — Kaniko build of the MTP image (nvidia/cuda base, tarball
  llama.cpp, `scripts/docker_fetch_models.py`).
- `scripts/docker_fetch_models.py` (new) — anonymous GGUF download for Kaniko (no heredoc/secret).
- `.gitignore` — block `.env*` / `*_token.txt`.
- `pyproject.toml` / `src/hackaithon_c/branding.py` / `CHANGELOG.md` — version 0.5.0 → 0.6.0.
- `notes/lessons.md` — durable lessons from items 2,3,5,6,7,8 above.

## Current state / next
- Phase A re-run on pod `6xiuqh1mde72if` (RTX 3090 community) passed the build + draft-mtp check;
  downloading the 15 GB models, then the entrypoint MTP smoke → `pred.csv` + timing.
- After Phase A is green: run Phase B (Kaniko) → push `hacamy12345/neko-core:gemma26b-q4-mtp-20260614`
  → PAUSE for owner before promoting the stable tag / leaderboard submit. Then README repro tag +
  git tag on the build commit. RunPod balance ~$9; spend so far ~$0.3.
