# Lessons (append-only)

Durable lessons learned while building Neko Core. Newest on top.

## 2026-06-14 — packaging the MTP image on RunPod (tar ownership + Kaniko destroys SSH)

- **Windows-created tarballs fail to extract as root on Linux: use `tar --no-same-owner`.**
  A context tarball built with Windows git-bash `tar czf` stamps Windows uid/gid
  (e.g. 197609/197121). GNU tar on the pod, running as root, tries to `chown` every entry
  to those nonexistent ids → `Cannot change ownership ... Invalid argument` → exit 2, and
  with `set -e`/`&&` the whole step dies. The gzip is fine (`gzip -t` passes); it is purely
  the ownership restore. FIX: always extract a Windows→pod tarball with
  `tar xzf ctx.tar.gz -C dest --no-same-owner`. (Bit two launches before I caught it.)
- **Running `/kaniko/executor` directly on a pod root CLOBBERS the pod's sshd.** Kaniko is
  built to BE the container: it deletes / (minus ignore-paths) and re-extracts the base
  image, which wipes the running sshd's host keys/libs → all new SSH sessions get
  `kex_exchange_identification: Connection reset`. So a Kaniko build run this way is BLIND
  (no SSH to monitor or read kaniko.log). Consequences/rules:
  - Do ALL verification (build steps, functional smoke) on the pod WHILE SSH is alive,
    BEFORE invoking the executor; treat the executor as the irreversible last step.
  - `--ignore-path=/workspace` preserves the context/auth/logs on /workspace, but NOT sshd.
  - Verify a Kaniko build's success by polling Docker Hub for the pushed tag, not via SSH.
  - The launch ssh (`setsid bash run.sh ... & disown`) TIMING OUT at 120s is EXPECTED — the
    run started; VERIFY (pgrep/log), never relaunch (double-run / double-load).
- **`set -o pipefail` + `grep -q` on a verbose command = false failure (SIGPIPE).** A check like
  `llama-server --help | grep -q draft-mtp || fail` FAILS under pipefail even when the match is
  found: `grep -q` exits on the first match and closes the pipe → the producer (`--help`, still
  writing) gets SIGPIPE (exit 141) → pipefail reports the pipe as failed. Symptom that misleads:
  the same check passes when run by hand (interactive shells have no pipefail). FIX: capture to a
  file then grep — `cmd >/tmp/out 2>&1 || true; grep -q PAT /tmp/out || fail`. (Docker `RUN` uses
  `/bin/sh` with no pipefail, so the identical line in a Dockerfile is fine — this only bites
  `set -uo pipefail` harness scripts.)
- **GitHub git-protocol is slow/flaky from rented pods; download a source tarball over HTTPS.**
  `git clone` (full history) of llama.cpp crawled at ~93 KB/s on a 3090 pod and a shallow
  `git fetch --depth 1 <sha>` died with `fatal: early EOF / invalid index-pack output`, while HF
  HTTPS downloads on the SAME pod were fast. git-pack negotiation/compression is the bottleneck.
  FIX: `curl -fsSL https://github.com/<org>/<repo>/archive/<sha>.tar.gz | tar xz --strip-components=1`
  — one plain HTTPS GET from codeload, no git-protocol. (Also: never omit `--depth 1` if you do use git.)
- **`pkill -f "<pattern>"` matches your OWN ssh command line → self-kill.** Running
  `ssh host 'pkill -9 -f "git clone"'` killed the ssh session itself (exit 255, no output) because
  the remote `bash -c` command line CONTAINS the string "git clone" (as the pkill argument), so
  `-f` (full-cmdline match) matched it. FIX: kill by process NAME (`pkill -9 git`, no `-f`), or use
  a pattern that cannot appear in your own command.
- **Poll/condition checks must ignore error text that echoes the thing being matched.** A monitor
  doing `if "A_DONE" in ssh_output` fired a false "done" because an ssh TIMEOUT error string echoes
  the failed command (`ls .../A_DONE .../A_FAILED`) → the marker name was present in the *error*, not
  the output. FIX: guard on `"(ssh err" not in output` before testing for the marker.
- **A dynamically-linked llama-server needs its libs on the path BEFORE any `--help`/run.** The
  built `llama-server` is a thin binary linking `libggml*.so` (in `build/bin/`). Running it without
  `LD_LIBRARY_PATH` (or the Dockerfile's `cp *.so /usr/local/lib && ldconfig`) makes even `--help`
  fail to load → misleading "feature missing" verdicts. Set the lib path before the capability check.

## 2026-06-11 — GPU selection economics (why A5000 community, and the real trade-off)

- **Match the GPU to the workload's bottleneck, not its size.** Gemma-4-26B-A4B is an MoE
  with ~4B ACTIVE params; token generation is memory-BANDWIDTH-bound, not compute-bound.
  A5000 (768 GB/s) ≈ A40 (696 GB/s) in bandwidth → similar tokens/sec for this model at
  **$0.16/hr vs $0.44/hr (2.75× cheaper)**. Measured: 6.3s/q on A5000 vs 4.6s/q on A40
  (~35% slower overall — the gap is mostly the 2014-era CPU doing prompt processing, not
  the GPU). For experiment batteries where wall-clock is flexible, community-cheap wins;
  for deadline-critical final runs, pay for secure/newer (no SIGILL roulette, no capacity
  churn).
- **The hidden price of community pods is HARDWARE AGE, not the GPU**: our $0.16 pod came
  with a Haswell CPU → prebuilt AVX512 wheels SIGILL'd → ~40 min + ~$0.10 lost to a
  source rebuild. Budget 30-60 min of incident slack into any community-pod plan.
- **Measurement validity > raw speed.** The battery deliberately runs in-process
  sequential llama-cpp-python — the EXACT contest-image runtime — instead of the 3-8×
  faster llama-server+workers path, because A/B numbers must be measured on the runtime
  that ships. Speed-mode is for after the winner is chosen, never for the measurement.

## 2026-06-11 (GPU session 2 + frontier research)

- **Cheap community pods trade CPU age for price.** A $0.16/hr A5000 pod came with a 2014
  Haswell CPU (no AVX512) → prebuilt llama-cpp wheels SIGILL with EMPTY logs. Diagnose
  with a tiny foreground run (`Illegal instruction` + exit 132), confirm via
  /proc/cpuinfo flags, fix by source-building with nvcc (often present but off PATH).
- **Never create the target of a future symlink.** A `mkdir /models` before
  `ln -sfn /workspace/models /models` silently turned the link into a real dir on the
  small container disk → 14GB extraction filled / and died. Use absolute volume paths in
  scripts instead of symlink conventions, and size containerDiskInGb ≥30 for CUDA images.
- **Labeled Vietnamese dev sets exist and are gold**: ViGEText (3,722 graduation-exam
  MCQs, 7 subjects, `{id,input,target}`, options inline as `A. ...` lines) downloads
  ungated → local per-subject accuracy without burning leaderboard submissions. Some HF
  datasets vanish (vietnamese-legal-qa) — always code a fallback.
- **Research before building paid off twice**: (1) the quant-stack audit found our GGUF
  may carry a recoverable multi-point loss (naive Q4_0 vs UD-Q4_K_XL); (2) evidence
  AGAINST popular tricks (self-verification −1…−17pp, elimination prompting −5…−14pp)
  stopped us from shipping harmful "obvious" features. Negative results are as valuable
  as positive ones.
- **Remote-script hygiene on Windows→pod**: Write file → scp → `tr -d '\r'` → bash.
  Inline ssh quoting, sed-based CRLF fixes, and PowerShell BOMs all caused real failures.

## 2026-06-10

- **Verify feedback against code + real data before acting.** A teammate's 6-point
  critique was ~80% right, but: one example set was claimed stale (it wasn't), one
  ordering detail was wrong (calc is prioritized *before* many_choice), and the true
  root cause of the routing bug was mis-framed (it's diacritic collision, not
  substring-vs-token). Trusting it verbatim would have produced the wrong fix.
- **Fake confidence hides everything.** Hard-coded per-path confidence made ~57 wrong
  answers invisible (79.5% sat at ≥0.88). Before chasing accuracy, build a *real*
  uncertainty signal (self-consistency / cross-model disagreement). You can't fix
  errors you can't see.
- **Diacritics are meaning-bearing in Vietnamese.** Stripping them for keyword
  matching collapses `tỉnh/tính/tinh`. The model never needed stripping — only the
  legacy router did. Prefer language-agnostic structural signals over keyword routing.
- **Suppressing reasoning then patching with hand-coded math is backwards.** Letter-
  only prompts (`no explanation`) hurt reasoning items; the ~7 bespoke calculation
  solvers are a symptom-patch that overfits the 463 public questions.
- **Overfit = transfer risk.** Anything tuned to 463 public items or to Vietnamese
  specifically is a liability on the 2000-question multilingual private test.
- **Notebook discipline.** Investigations live in `notes/` with file:line evidence,
  one dated file per topic; `lessons.md` captures the durable takeaways.

## 2026-06-12 (GPU session — PowerShell→ssh→bash quoting)

- **PowerShell→ssh→bash inline quoting: use a SINGLE-QUOTED outer string.** Repeatedly
  hit parser errors running inline ssh from PowerShell: `<`, `||`, `$(...)`, `\"` inside a
  DOUBLE-quoted PS string get interpreted by PowerShell (`The '<' operator is reserved`,
  `'||' is not a valid statement separator`), or the `\"` escaping unbalances quotes so PS
  sees bash operators bare. FIX: wrap the remote command in **single quotes** so PowerShell
  passes it to ssh verbatim and bash parses it —
  `ssh ... root@host 'for d in a b; do n=$(wc -l < f); echo "$d $n"; done'`.
  Bash `$var`/`$(...)` stay intact (PS does not expand inside single quotes).
- **For anything non-trivial, still prefer: write .sh file → scp → `tr -d '\r'` → bash.**
  The single-quote trick is for quick one-liners; multi-line/heredoc scripts must go through
  a file (CRLF + quoting bite otherwise). Both confirmed this session.

## 2026-06-12 (GPU session — gemma-4-31B Q4 VRAM / n_ctx)

- **gemma-4-31B Q4_0 (~17.7GB) OOMs at n_ctx=8192 on a 24GB GPU** ("Failed to create
  llama_context" → harness fell back to heuristic, GPU idle 0%). Model weights ~17.7GB +
  8192-ctx KV + compute buffer exceeded 24GB. **Fix: n_ctx=4096** (HACKC_LLAMACPP_N_CTX) →
  ~21GB, fits, real answers. Proxy questions are short so no truncation; but the REAL 463
  has max ~3.4k-token inputs + 2048 reasoning ≈ 5.5k needed → for the 463/Docker run use
  n_ctx≈6144 (verify it still fits 24GB) or trim reasoning_max_tokens.
- **Operational point favoring 26B for the submission:** gemma-4-26B-A4B is an MoE (~14.4GB
  Q4) and runs fine at n_ctx=8192 on 24GB; the dense 31B is tight on VRAM AND slower. If 31B
  only buys ~+2pp, the VRAM/latency cost (and the risk it OOMs on the BTC GPU at an unknown
  VRAM) is a real tradeoff to weigh — the Docker must pin n_ctx to whatever fits the judges'
  hardware. Always measure VRAM headroom before committing a bigger model to the image.

## 2026-06-12 (the "stalled GPU" was MY env-var bug, not community instability)

CORRECTION - I first blamed a community pod for "stalling"; the real root cause was a bug
in my quant run script. Recording the truth so the misdiagnosis is not repeated.

- **ROOT CAUSE: the local client reads the model PATH from `HACKC_LOCAL_MODEL_PATH` (env),
  NOT from a config `runtime.local_model_path` key.** `run_quant.sh` set the path only in the
  per-quant config file and forgot to `export HACKC_LOCAL_MODEL_PATH`, so the client fell back
  to the Dockerfile default `/models/gemma-4-26B_q4_0-it.gguf` (absent on a raw pod) ->
  `RuntimeError: Local model file not found` -> caught per-question -> heuristic fallback +
  `_solve_with_retry` exponential-backoff `time.sleep`. Symptom: python in `nanosleep`, RSS
  ~24MB (Llama never constructed), GPU cold (0% util, ~25C, ~0 MiB), checkpoint count crawling.
  `run_26b.sh` (the sweep) DID export the env -> worked; the diff was a one-line omission.
  The working sweep is the template: always export
  HACKC_PROVIDER/HACKC_LOCAL_MODEL_PATH/HACKC_LLAMACPP_N_CTX/N_GPU_LAYERS before the run.
- **DIAGNOSTIC that actually localises this:** when a run looks stalled, read the first
  checkpoint entry's `strategy`/`fallback_reason`/`raw_answer`. A `*_after_error` strategy with
  `raw_answer=solver_error=...` names the exact exception; a healthy run shows
  `strategy=gemma_self_consistency, fallback_reason=None`. Cold GPU + low RSS = the model never
  loaded -> check the PATH/env FIRST, do not assume a bad pod. A standalone
  `python -c "from llama_cpp import Llama; Llama(path,...)"` loading fine while the harness
  "stalls" is the tell that it is a harness/config path issue, not hardware.
- **SECURE-vs-COMMUNITY — COST-FIRST rule (corrected):** Do NOT blanket-avoid community.
  This session's "stalls" were MY env-var bug on BOTH a community AND a SECURE pod, not
  community instability — so community is not the villain. **Rule: if community is meaningfully
  cheaper, rent COMMUNITY; only when the price is about the same, prefer SECURE** (dedicated
  GPU, can't be reclaimed mid-run — a small reliability edge worth taking only for free). The
  real reliability win is the run discipline below (reuse script + 2-min health-verify +
  kill-verify-zero), not the cloud tier. Community's genuine cost is older CPUs (prebuilt
  wheels may SIGILL → source-build) — budget for that, not for "it will stall."

## 2026-06-12 (GPU RUN PLAYBOOK - mandatory; this session wasted ~2h on avoidable mistakes)

Honest post-mortem: a quant measurement that should have taken ~40 min took >2h and produced
nothing usable until the 4th relaunch, due to a CASCADE of my own mistakes. Follow this
checklist for EVERY GPU run; each rule maps to a concrete failure below.

### The cascade that happened (so it is not repeated)
1. **Wrote a NEW run script instead of reusing the proven one.** `run_quant.sh` dropped the
   one line `export HACKC_LOCAL_MODEL_PATH=...` that the working `run_26b.sh` had. The client
   reads the model PATH from ENV, not config -> every question fell to heuristic fallback +
   retry-sleep, model never loaded, GPU cold. Burned ~80 min before I looked at WHY.
2. **Misdiagnosed it as community-pod instability** and re-rented a SECURE pod - the new pod
   had the SAME bug (it was my script, not the hardware).
3. **Created a double-run**: relaunching without fully killing the prior detached run.sh left
   TWO run.sh racing on one GPU (one on Q8, one on Q6), contending for VRAM and corrupting
   outputs.
4. Only after reading the checkpoint's `fallback_reason` did the real cause surface.

### MANDATORY checklist (do in order, every time)
1. **REUSE the last known-good script.** Copy `run_26b.sh` (the sweep that worked) and change
   only what is needed. If you must edit, `diff` against the working one and confirm the env
   exports survive: `export HACKC_PROVIDER=local_llamacpp HACKC_LOCAL_MODEL_PATH=$MP
   HACKC_LLAMACPP_N_CTX=8192 HACKC_LLAMACPP_N_GPU_LAYERS=-1` BEFORE every `python -m
   hackaithon_c.run`. The model path lives in ENV, never trust config `local_model_path`.
2. **Kill-verify-ZERO before any (re)launch.** `pkill -9 -f hackaithon_c.run; pkill -9 -f
   /workspace/run.sh` repeated until BOTH `pgrep` count = 0 AND `nvidia-smi` shows ~0 MiB.
   Only then launch. Never relaunch on top of a possibly-alive detached run (double-run).
3. **Launch exactly once** via `setsid env PYTHONUNBUFFERED=1 bash run.sh </dev/null >log 2>&1
   & disown`. The ssh call will TIME OUT at 120s - that is EXPECTED, the run started. Do NOT
   relaunch because of the timeout; verify instead (step 4).
4. **HEALTH-VERIFY within 2 MINUTES of launch - the single most valuable habit.** Confirm ALL:
   - exactly **1** `hackaithon_c.run` python instance (`pgrep -af ... | wc -l` == 1),
   - GPU **hot**: `nvidia-smi` >80% util + model-size VRAM (Q4~15 / Q6~22 / Q8~28 GB),
   - first checkpoint entry is **real**: `strategy=gemma_self_consistency, fallback_reason=None`
     (NOT `*_after_error` / `raw_answer=solver_error=...`).
   If GPU is cold OR the strategy is a fallback -> STOP NOW, fix, relaunch. Catching this at
   2 min instead of 80 min is the whole game.
5. **A "stall" is diagnosed by the checkpoint, not the pod.** Cold GPU + low RSS (~24MB =
   Llama never constructed) + `fallback_reason` set = model-not-loaded (path/env), not a bad
   GPU. A standalone `Llama(path,...)` that loads fine proves the hardware is OK.
6. **Always terminate the pod after pulling results** (podTerminate, User-Agent header).

### Time-economics reminder
Every avoidable relaunch on a 28GB-model run costs ~5-10 min (reload) + my attention. The 2-min
health-verify (step 4) is the cheapest insurance there is - it would have saved this whole session.

## 2026-06-13 (MTP benchmark — community-pod build + measurement gotchas)

- **CUDA `cmake --build -j` (unlimited) OOM-kills on RAM-limited community pods.** A 3090
  community pod (62 GB RAM) ran ~245 parallel nvcc/cc1plus jobs and got Error 137 (OOM). FIX:
  cap parallelism, e.g. `cmake --build build -j 4 --target llama-server` (each CUDA TU ~2-4 GB).
  `scripts/gpu/run_mtp_server.sh` uses unlimited `-j`; cap it on low-RAM pods.
- **draft-mtp lossless check needs temp=0.** Benchmarking at temp>0 (reasoning prompt) makes
  generation stochastic, so MTP output never byte-matches the baseline and the
  `content_matches_baseline` gate always "fails" spuriously. To prove losslessness, run a
  greedy (temp=0) pass. The speedup measurement itself is still valid at temp>0.
- **MoE MTP speedup is modest:** 26B-A4B gave ~1.37x best (n-max=2), acceptance 0.70, falling to
  1.07x at n=6 (acceptance 0.40). The 1.4-2.2x literature numbers are dense-model/B200 best-cases.
- **D-state compile procs survive `kill -9` until their syscall returns** — after killing a CUDA
  build, wait ~10-15 s and re-check before relaunching, or the new build contends for RAM.
