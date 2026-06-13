# MTP (Multi-Token Prediction) — Vòng-2 Time lever (2026-06-12)

## What it is

A speculative-decoding scheme: the model drafts several future tokens in one pass, then the
**main model verifies them in parallel** and keeps only the accepted ones. Because the main
model is always the final arbiter, the output is **bit-identical to non-MTP greedy/sampled
decoding → ZERO accuracy loss.** It is purely a *speed* technique, orthogonal to quant
(which is the accuracy lever).

## Why it matters for us (Vòng-2 Time score = 10 pts)

- **1.4–2.2× faster** running GGUFs; **Gemma-4 QAT + MTP = 1.5–2.2×**. Real-world ~1.6×
  typical (draft acceptance ~0.70); 2.2× is best-case.
- Available for **26B-A4B** — the exact model we ship. No accuracy trade-off.
- Our 26B does 2000 private q in ~1.6 h → with MTP ~**0.7–1.1 h**. Free Time-score win.
- +~2 GB VRAM headroom.

## Engine support / how to run

- Merged into **llama.cpp on 2026-06-07** (PR ggml-org/llama.cpp#23398).
- CLI flags: `--spec-type draft-mtp --spec-draft-n-max N` (start N=2; try 1–6, hardware-dependent).
- Bench data: gemma-4-12b 52→162 tok/s on a B200 (0.70 draft acceptance); 31B ~24→40 tok/s (~1.64×).
- unsloth ships the MTP draft weights in the repos (an `MTP/` subfolder, e.g.
  `unsloth/gemma-4-26B-A4B-it-GGUF` → `MTP/...`). Confirm the exact draft file for 26B-A4B at run time.

## OPEN — must verify before adopting (honesty)

1. **Does `llama-cpp-python` (our binding) expose MTP/spec-decode?** The merge is in the
   llama.cpp C++ core; the Python wrapper must (a) be built after 2026-06-07 and (b) expose
   the draft-mtp speculative params via the `Llama(...)` constructor. If the binding does NOT
   expose it, options: (i) upgrade/patch llama-cpp-python, (ii) switch the runtime to the
   `local_server` provider driving the llama.cpp HTTP server (`llama-server --spec-type
   draft-mtp ...`) which definitely supports it, (iii) call the CLI. This is a real
   integration task, not free.
2. Confirm the MTP draft GGUF for 26B-A4B + the exact load path.
3. Measure the REAL speedup on our hardware (acceptance rate varies); 2.2× is best-case.

## Plan

- Orthogonal to quant: ship BOTH (e.g. Q6_K + MTP = more accurate *and* faster).
- Same-GPU-session test (after the quant run, before terminating the pod): download the
  26B-A4B MTP draft, run a timed generation WITH vs WITHOUT `--spec-type draft-mtp`, record
  tok/s + that outputs match. First via llama.cpp CLI/llama-bench (proves the GGUF+flags),
  then verify whether `llama-cpp-python` can drive it for the offline Docker.
- If the Python binding can't drive MTP, evaluate the `local_server` provider path (the
  harness already has a `local_server` provider) — llama-server supports the flags natively.

## Session 1 status (2026-06-12) — STOPPED at a GPU-offload issue (resume here)

Got the full pipeline working except the final speed measurement:
- llama.cpp CLI built fine with CUDA (CUDAToolkit 12.4, `libggml-cuda.so.0.15.1` present).
- main QAT Q4 (14G) + MTP draft `mtp-gemma-4-26B-A4B-it.gguf` (441M) downloaded fine.
- **BLOCKER: `llama-cli -ngl 999` ran on CPU, not GPU** (GPU 0% util, CPU 99%, a 400-token
  gen took >7 min; even a 20-token test timed out at 120s). The CUDA backend `.so` IS built
  and co-located in `build/bin/` next to `llama-cli`, but the runtime did not offload.

RESUME PLAN (next session, ~20 min):
1. Run `llama-cli -m main.gguf -ngl 999 -n 20 -p Hi` with **FULL visible output** (do NOT grep)
   and read the load lines — confirm whether it says "offloaded N/Y layers to GPU / using
   CUDA0" or falls back to CPU. That output names the cause.
2. Likely fixes to try, in order: (a) build ALL targets (`cmake --build build -j`, not just
   `--target llama-cli`) so the backend registry links; (b) set `LD_LIBRARY_PATH=build/bin`
   or run from build/bin so it finds `libggml-cuda.so`; (c) check the binary actually links
   CUDA (`ldd llama-cli | grep cuda`); (d) try `--device CUDA0`.
3. Fix the bench script: do NOT pipe llama.cpp through `grep` (it hid the offload/load info);
   keep full output, parse tok/s afterwards.
4. Then run baseline vs `--spec-type draft-mtp --spec-draft-n-max 2/4/6`, KV cache f16,
   record tok/s + acceptance. Assets staged in `C:/Users/Admin/AppData/Local/Temp/pod_mtp/`
   (run_mtp.sh, prov_mtp.py, launch_mtp.py). Pod terminated; re-provision per the cost-first rule.


## Session 2 update (2026-06-13) — GPU offload SOLVED; blocked on llama.cpp master tooling

Progress beyond Session 1 (then cancelled by owner; pod terminated):
- **GPU offload now CONFIRMED WORKING.** `llama-cli --list-devices` sees `CUDA0: RTX 4090`;
  `ldd libggml-cuda.so` resolves all CUDA libs; the model loads to GPU (~20 GB used). The
  Session-1 "ran on CPU" was a misread — the real issue is the CLI never EXITS (below). Build
  fix that worked: `cmake --build build --target llama-cli` ONLY (building all targets or
  llama-server pulls in `tools/ui/ui.cpp`, which has a master-branch regression:
  `static const unsigned char asset_60_data[] = {};` — a zero-size array C++ error).
- **BLOCKER: llama.cpp master (build b1-d8a24cc) made `llama-cli` an interactive chat REPL that
  will not do a clean one-shot generation.** With stdin=/dev/null it loops printing `> ` to EOF
  forever (a 1.2 GB log in 240 s) and never exits. BOTH `-no-cnv` and `-st` (--single-turn)
  FAILED to suppress the REPL on this build. So llama-cli cannot be used to benchmark here.
- **The right path (production-aligned) is `llama-server` (HTTP), not llama-cli** — it is also
  the harness `local_server` provider path for the Docker. llama-server failed to build for the
  same `tools/ui/ui.cpp` zero-size-array reason; FIX APPLIED:
  `sed -i 's/\[\] = {};/[] = {0};/g' build/tools/ui/ui.cpp` then rebuild `--target llama-server`.
  The rebuild + the HTTP measurement (run_server_mtp.sh, staged in pod_mtp/) were cancelled
  before completing.

### RESUME (next session, ~25 min) — use llama-server, skip llama-cli
1. Re-provision (cost-first). Reuse pod_mtp/ assets: run_mtp.sh (builds llama-cli+CUDA, downloads
   main Q4 + draft) and run_server_mtp.sh (the HTTP measurement). 
2. Patch tools/ui/ui.cpp zero-size arrays (`[] = {};` -> `[] = {0};`) BEFORE building llama-server;
   OR check out a STABLE llama.cpp release TAG (post 2026-06-07 MTP merge) to avoid the master
   regression entirely (cleaner — no patch, and llama-cli may be non-interactive there too).
3. Run `run_server_mtp.sh`: starts llama-server with `-m main --model-draft mtp-draft
   --spec-type draft-mtp --spec-draft-n-max {2,4,6} -ngl 999 --device CUDA0 -fa on` (KV f16),
   curls /completion, reads `timings.predicted_per_second` + draft accept counts. Compare to the
   baseline (no --model-draft). Expect 1.4-2.2x.
4. If MTP confirms a real speedup, wire the Docker to the `local_server` provider driving
   llama-server with the MTP flags (the harness already has a local_server provider).

### Strategic note
MTP is a Vong-2 TIME-score lever (lossless speed), nice-to-have, NOT blocking. Per the error
analysis (`error-analysis-31-disagreements-2026-06-12.md`), the bigger Vong-2 wins are already
shipped (bulletproof Docker, Idea doc) and the accuracy question is settled (88.55 near ceiling).
Resume MTP only when picking up Vong-2 polish.
