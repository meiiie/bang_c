# RunPod setup gotchas — quick reference (avoid re-debugging these)

Every setup error hit while running Neko Core on RunPod, with the one-line fix. Read before
writing a new pod run script. Base image used: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`.
The golden rule: **copy a script that already ran clean and change only what's needed** — most
of these were caused by writing a fresh script that dropped a line the working one had.

## Provisioning / connection
- **urllib gets HTTP 403 from the RunPod GraphQL API.** Their WAF blocks the default
  `python-urllib` User-Agent. FIX: add header `"User-Agent": "curl/8.4.0"` to every request.
- **`podFindAndDeployOnDemand` returns "no instances available" / "SUPPLY_CONSTRAINT".** A given
  GPU/cloud combo can be out of stock. FIX: loop over a candidate list of (gpuType, cloudType)
  and take the first that deploys. Cost-first: try cheaper community first unless price ≈ SECURE.
- **sshd not reachable right after deploy.** Image pull takes ~10-15 min on first boot. FIX:
  poll the SSH port, then poll `ssh echo READY`, up to ~15 min, before doing anything.
- **The detached-launch ssh call TIMES OUT at 120s but the run STARTED.** `setsid bash run.sh &`
  keeps the channel open so `subprocess.run` times out — this is EXPECTED, NOT a failure. FIX:
  ignore the timeout; VERIFY the run started instead (never relaunch on the timeout → double-run).

## Toolchain missing on the base image (install at the top of run.sh)
- **`cmake: command not found`** — the devel image has CUDA + nvcc but NOT cmake/build-essential.
  Needed only if you build from source (e.g. llama.cpp CLI). FIX:
  `apt-get update -qq && apt-get install -y -qq cmake build-essential git libgomp1`.
- **`ModuleNotFoundError: No module named 'huggingface_hub'`** — not preinstalled. FIX:
  `python -m pip install "huggingface-hub>=0.32,<1"` before any `hf_hub_download`.
- **Prebuilt `llama-cpp-python` CUDA wheel SIGILLs on old (community) CPUs** (no AVX512). FIX:
  install the prebuilt wheel first (`--extra-index-url .../whl/cu124`), and on import failure
  fall back to a source build (`CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 pip install ... --no-binary`).

## Running the Neko harness on a pod
- **Model path comes from ENV, not config.** The local client reads `HACKC_LOCAL_MODEL_PATH`;
  a `runtime.local_model_path` key in the config JSON is IGNORED → it falls back to the Docker
  default `/models/gemma-4-26B_q4_0-it.gguf` (absent on a raw pod) → `RuntimeError: Local model
  file not found` → every question silently becomes a heuristic FALLBACK + retry-sleep (cold GPU,
  RSS ~24MB). FIX: before `python -m hackaithon_c.run`, always
  `export HACKC_PROVIDER=local_llamacpp HACKC_LOCAL_MODEL_PATH=$MP HACKC_LLAMACPP_N_CTX=8192
  HACKC_LLAMACPP_N_GPU_LAYERS=-1`. (`run_26b.sh` is the known-good template.)
- **31B Q4 OOMs at n_ctx=8192 on a 24GB GPU.** FIX: n_ctx=4096 (~21GB) or use ≥40GB. 26B-A4B
  (MoE ~15GB) fits 24GB at n_ctx=8192 — prefer it.

## MTP (llama.cpp CLI) specifics
- Build: `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=$CC` where
  `CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .)`
  (A40/A6000=86, 4090=89). Target `llama-cli` / `llama-server`. ~8 min compile.
- Run: `-m <main.gguf> --model-draft <mtp-draft.gguf> --spec-type draft-mtp --spec-draft-n-max 4
  -ngl 999 -fa on`. main = QAT Q4_0; draft = `mtp-gemma-4-26B-A4B-it.gguf`.
- **GOTCHA: a quantized (q8_0) KV cache makes draft-mtp acceptance 0%.** Keep KV cache at f16
  (the default) — do NOT pass `-ctk q8_0 -ctv q8_0`.

## Process hygiene (the rules that actually prevent wasted hours)
1. **REUSE the known-good run script**; `diff` any edits; keep the env exports.
2. **Kill-verify-ZERO before any relaunch:** `pkill -9 -f run.sh; pkill -9 -f hackaithon_c.run`
   repeated until `pgrep` count = 0 AND `nvidia-smi` ~0 MiB. Else you get a DOUBLE-RUN
   (two processes racing on one GPU, VRAM contention, corrupted outputs).
3. **HEALTH-VERIFY within 2 minutes of launch:** exactly 1 process, GPU hot (>80% + model-size
   VRAM), first checkpoint `strategy=gemma_self_consistency, fallback_reason=None`. Catching a
   bad launch at 2 min instead of 80 min is the whole game.
4. **Diagnose a "stall" via the checkpoint's `fallback_reason`, not the pod.** Cold GPU + low RSS
   = model never loaded (path/env), not a bad GPU. A standalone `Llama(path,...)` that loads
   proves the hardware is fine.
5. **`podTerminate` after pulling results** (User-Agent header). Never leave a billing pod.

## Cache wins
- A `git clone`+build or a 14-28GB model download is cached on the pod disk; a relaunch that
  guards with `if [ ! -x .../llama-cli ]` / `hf_hub_download` (skips if present) re-enters in
  seconds. So a setup-error relaunch is cheap — fix the one line and re-run, don't re-provision.
