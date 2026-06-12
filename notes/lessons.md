# Lessons (append-only)

Durable lessons learned while building Neko Core. Newest on top.

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

## 2026-06-12 (RunPod SECURE vs COMMUNITY — use SECURE for any multi-hour run)

- **COMMUNITY pods are NOT reliable for long runs.** A community A6000 stalled mid-run at
  320/463: the GPU went COLD (nvidia-smi 0% util, 25°C, 1 MiB used — the model fell out of
  VRAM) while the python process limped on CPU/hung. No OOM, no Xid in dmesg — the host
  simply reclaimed/oversubscribed the GPU. ~80 min + the whole session wasted. This is the
  SAME class of failure as the earlier 24GB GPU crash; community = someone else's machine
  rented back (Airbnb-for-GPU), so availability of the GPU is not guaranteed mid-run.
- **RULE: rent SECURE for anything ≥~30 min or that must finish (quant runs, full-463
  sweeps, the real submission run).** SECURE = RunPod's own T3/T4 datacenter, dedicated GPU,
  ~$0.8/h for A6000/A40 vs ~$0.3-0.4/h community. The ~$0.4/h premium is trivial next to a
  lost session. COMMUNITY is only for short, restartable probes you can afford to lose.
  Confirmed stable this session: RTX 4090 SECURE (full sweep), A6000 SECURE (31B), A40 SECURE.
- **Diagnosing a stalled GPU run (vs just slow):** check `nvidia-smi` util+temp. A working
  llama.cpp run keeps the GPU ~85-95% util and 60-80°C. **0% util + low temp + a flat
  checkpoint line count over a 90s window = STALLED/DEAD, not slow** — kill and re-provision
  on SECURE; do not wait it out.
