# MTP resume note - 2026-06-13

Status: local research + script prep only. No RunPod spend was started in this
session.

## Current conclusion

CUDA/GPU offload is no longer the active blocker. The latest committed session
notes record a successful GPU load path: llama.cpp sees the RTX 4090, the CUDA
backend links, and the model allocates roughly model-sized VRAM.

Upstream status checked on 2026-06-13: `llama.cpp` PR `#23398` was merged into
`ggml-org:master` on 2026-06-07. It adds Gemma 4 MTP support and documents a
`llama-server ... --spec-type draft-mtp --spec-draft-n-max 4` path. A Google
Hugging Face discussion for `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` also
points users to `llama-server -m <main> --model-draft <assistant-MTP>
--spec-type draft-mtp --spec-draft-n-max 4`.

Important caveat: the PR author and follow-up reports show speedup is
hardware/model/KV-cache dependent, with some MoE or q8 KV runs producing no
speedup or even slowdown. Treat MTP as a measured Vong-2 speed candidate, not an
automatic win.

The active blocker is `llama.cpp` tooling/measurement:

- the tested master build made `llama-cli` behave like an interactive REPL, so
  `-no-cnv` and `-st` did not produce a clean one-shot benchmark;
- `llama-server` is the correct path because it matches the harness
  `local_server` provider and exposes HTTP/OpenAI-compatible inference;
- one generated `tools/ui/ui.cpp` asset bug was observed and patched in the pod
  run by changing empty arrays from `[] = {};` to `[] = {0};`.

The reusable prepared script is now tracked at:

```text
scripts/gpu/run_mtp_server.sh
```

It benchmarks `llama-server` baseline versus `--spec-type draft-mtp` for
`--spec-draft-n-max` values `1,2,4,6`, keeps KV cache f16, captures full server
logs, and writes summaries under `/workspace/mtp_server_logs/`.

Offline hardening added after the first script prep:

- `OWNER_SIGNOFF=1` is now required before the script does any GPU/model work;
- the benchmark port is checked before `nvidia-smi`, build, or model download,
  so an occupied port fails before spending GPU/build time;
- global cleanup trap kills only the child `llama-server` PID started by the
  script and marks `/workspace/FAILED` on unexpected failure;
- the script no longer `pkill`s by port pattern; it refuses to run if the port
  is already occupied;
- llama.cpp `git fetch` and `checkout --detach FETCH_HEAD` failures now fail
  closed instead of silently benchmarking the wrong ref;
- `launch-config.json` records the benchmark config and model paths;
- `results.jsonl` and `summary.txt` include generated-content SHA-256 hashes
  and `content_matches_baseline` for MTP runs;
- default `MEASURE_REQUESTS=3` records repeated measurements per config and
  reports median tok/s + median speedup instead of trusting one noisy request;
- `REQUIRE_CONTENT_MATCH=1` makes non-lossless MTP output fail before `SRV_DONE`;
- `REQUIRE_SPEC_INIT=0` and `REQUIRE_DRAFT_ACCEPTANCE=0` keep log/metric wording
  drift as warnings by default, but can be set to `1` for stricter debug runs;
- config now has a non-default `gemma26b-q4-local-server` runtime profile, and
  tests verify the harness posts to `/v1/chat/completions` for `local_server`.

## Next GPU steps

After owner sign-off for RunPod spend:

1. Provision a fresh GPU pod.
2. Ensure the pod has access to gated Gemma downloads via `HF_TOKEN` or
   `HUGGING_FACE_HUB_TOKEN` in the environment.
3. Copy `scripts/gpu/run_mtp_server.sh` to the pod and run it with `bash`.
   Use `OWNER_SIGNOFF=1 bash run_mtp_server.sh`; the script writes
   `/workspace/mtp_server_logs/run.log` itself.
4. Watch `/workspace/mtp_server_logs/run.log` until `/workspace/SRV_DONE`
   appears.
5. Pull the whole `/workspace/mtp_server_logs/` directory before terminating.
6. Terminate the pod.
7. Record measured tok/s, draft acceptance, wall time, GPU, VRAM, and llama.cpp
   commit hash in `notes/mtp-direction-2026-06-12.md` or a follow-up note. Also
   record whether `content_matches_baseline=true` and whether any spec-init or
   draft-acceptance warnings appeared in `summary.txt`.
8. Run the offline assessment locally or on the pod:

   ```bash
   python scripts/assess_experiment_results.py \
     --mtp-summary /workspace/mtp_server_logs/summary.txt \
     --min-mtp-speedup 1.4 \
     --summary-json /workspace/mtp_server_logs/experiment-assessment.json
   ```

   A PASS means the speed candidate is ready for owner review, not automatic
   Docker/runtime promotion.

## Integration decision tree

Prefer no solver changes. MTP is a runtime/provider acceleration.

If `llama-cpp-python` exposes draft-MTP constructor/server params by the time we
integrate:

- add config/env fields in `LocalLlamaConfig`;
- keep provider `local_llamacpp`;
- add focused tests for env/config plumbing.

If it does not expose draft-MTP:

- use the existing `local_server` provider in `model_client.py`;
- package `llama-server` and the MTP draft GGUF in the final image;
- make the entrypoint start `llama-server`, wait for health, then run the
  existing harness against `http://127.0.0.1:8080/v1`;
- add a runtime profile for the MTP server path instead of branching in
  `solver.py`.

## Verification story before shipping

- llama.cpp GPU proof: full logs show CUDA backend loaded and layers offloaded.
- MTP proof: measured speedup and draft acceptance on the same GPU as baseline.
- Decision proof: `scripts/assess_experiment_results.py` passes on the pulled
  `summary.txt` using an explicit speedup threshold.
- Output proof: deterministic sample answers match baseline; for harness runs,
  compare traces and require changed answers = 0.
- Contract proof:
  - `python -m unittest discover -s tests -v`
  - `python -m compileall -q src`
  - `.\neko-core.ps1 --doctor`
  - `python -m hackaithon_c.run --policy`
  - dry-run contract check
  - Docker smoke mounted `/data` and `/output`
  - `--check-submission output/pred.csv`

## Do not repeat

- Do not benchmark MTP with `llama-cli` one-shot on the current tested master.
- Do not benchmark with live `grep`; keep full llama.cpp load logs.
- Do not use q8 KV for draft-MTP until measured otherwise; prior notes report
  zero acceptance with quantized KV.
- Do not promote MTP from claims alone. Upstream PR data includes good speedups
  but also hardware/model cases with weak or negative speedup.
- Do not edit prompt/solver behavior for MTP. Accuracy path must remain the
  measured 26B Q4 self-consistency + safety lever unless a separately measured
  accuracy change wins.

## Sources checked

- `notes/session-2026-06-12.md`
- `notes/mtp-direction-2026-06-12.md`
- `notes/error-analysis-31-disagreements-2026-06-12.md`
- `notes/runpod-setup-gotchas.md`
- `configs/default.json`
- `src/hackaithon_c/model_client.py`
- `src/hackaithon_c/local_client.py`
- `Dockerfile.gemma-local`
- `docker/neko-entrypoint.sh`
- `scripts/gpu/run_mtp_server.sh`
- llama.cpp PR 23398: https://github.com/ggml-org/llama.cpp/pull/23398
- llama.cpp issue 24266, negative speed report when MTP/other spec modes are
  mixed: https://github.com/ggml-org/llama.cpp/issues/24266
- Hugging Face discussion for Gemma 4 QAT Q4_0 GGUF MTP usage:
  https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf/discussions/4
- Google Gemma llama.cpp integration:
  https://ai.google.dev/gemma/docs/integrations/llamacpp

## Session 5 offline prep

No GPU/RunPod spend. Claude Code Opus (`--model opus --effort max`) reviewed
the current uncommitted worktree and found no blocking/high AGENTS.md issues.
Its highest-value no-GPU finding was that MTP had a benchmark script and a
`local_server` provider, but no local end-to-end proof of the production path:
start llama-server, wait for health, run the harness through `local_server`, and
write `pred.csv`.

Implemented the no-GPU part of that path:

- `docker/neko-entrypoint.sh` now supports `NEKO_LOCAL_SERVER_MODE=1`. In this
  mode it requires `llama-server`, the main GGUF, and the MTP draft GGUF;
  starts `llama-server` with `--spec-type draft-mtp`, f16 draft KV, and current
  draft flags; polls `/health`; exports `HACKC_PROVIDER=local_server` and
  `HACKC_LOCAL_SERVER_URL`; then runs the existing harness. Default non-server
  entrypoint behavior is unchanged.
- `tests/test_throughput.py` now includes a local OpenAI-compatible HTTP stub
  that runs the real harness with `--provider local_server --strategy direct
  --workers 2` and verifies a contract-valid `pred.csv`.
- Static tests assert the server-mode entrypoint requires model files, starts
  draft-MTP before handing control to the harness, waits for health, and cleans
  up the child server process.
- A dynamic fake-`llama-server` smoke now runs the actual
  `docker/neko-entrypoint.sh` in `NEKO_LOCAL_SERVER_MODE=1`: the fake server
  receives `/health`, the harness writes `pred.csv` through `local_server`, and
  the server port is closed after the entrypoint exits. The entrypoint also
  supports `NEKO_PYTHON_BIN` for distro images where `python3` exists but
  `python` does not.
- Claude Code review caught a shell-scoping risk where an `EXIT` trap might not
  see a `local` server PID after a successful function return. The entrypoint
  now stores the child PID in `NEKO_LOCAL_SERVER_PID`, which outlives the
  function scope; the fake-server smoke covers the success path.

Verification:

```powershell
bash -n docker/neko-entrypoint.sh
$env:PYTHONPATH = "$PWD/src"; python -m compileall -q src tests scripts
git diff --check
$env:PYTHONPATH = "$PWD/src"; python -m unittest tests.test_throughput -v
$env:PYTHONPATH = "$PWD/src"; python -m hackaithon_c.run --policy
$env:PYTHONPATH = "$PWD/src"; python -m unittest discover -s tests -v
```

Results: `bash -n` exit code `0` (with unrelated WSL config warnings),
`compileall` pass, `git diff --check` pass with CRLF warnings only,
`tests.test_throughput` pass (`23` tests), policy `PASS`, and full unittest
pass (`260` tests).

Remaining shipping work after owner sign-off: build/package the actual
`llama-server` binary and MTP draft GGUF in the final Docker image, then run the
GPU MTP measurement and offline assessment on pulled logs before deciding
whether to promote server mode.

## Session 6 offline prep

No GPU/RunPod spend. Verified the active Claude Code terminal is Opus 4.8 with
interactive `/effort ultracode`. `claude --help` shows scripted CLI effort
levels `low, medium, high, xhigh, max`, so project docs now use
`claude -p --model opus --effort max` for non-interactive reviews.

Added a CPU-only prompt exporter for more representative MTP measurements:

- `scripts/export_mtp_benchmark_prompt.py` reads a contest-shaped input file,
  selects one item (`first`, `longest`, or `median-length`), and emits the same
  production prompt shape used by the harness (`reasoning`, `direct`, or
  `reading`).
- It writes both a completion-style prompt and OpenAI chat `messages`, plus
  metadata with only `qid_sha256`; it does not load answers, call a model, or
  write `pred.csv`.
- `scripts/gpu/run_mtp_server.sh` can now set `BENCH_INPUT_PATH` to build this
  prompt before GPU work starts. It defaults to the OpenAI-compatible
  `/v1/chat/completions` endpoint, sends `messages` with `max_tokens`, records
  prompt source metadata, and uses `N_PREDICT=2048` by default to match the
  production reasoning cap more closely.
- `PROMPT_FILE` and `PROMPT` still take precedence for ad hoc debugging; if no
  prompt source is provided, the script falls back to its small built-in toy
  prompt.

Verification:

```powershell
bash -n scripts/gpu/run_mtp_server.sh
$env:PYTHONPATH = "$PWD/src"; python -m unittest tests.test_candidate_analysis.MtpBenchmarkPromptExportScriptTest tests.test_throughput.MtpServerScriptTests -v
python scripts/export_mtp_benchmark_prompt.py --input tests/fixtures/multilingual_gold.json --selection longest --prompt-mode reasoning --prompt-out output-mtp-prompt-check/prompt.txt --messages-out output-mtp-prompt-check/messages.json --metadata-out output-mtp-prompt-check/metadata.json
bash scripts/gpu/run_mtp_server.sh
$env:PYTHONPATH = "$PWD/src"; python -m compileall -q src tests scripts
git diff --check
$env:PYTHONPATH = "$PWD/src"; python -m hackaithon_c.run --policy
$env:PYTHONPATH = "$PWD/src"; python -m unittest discover -s tests -v
```

Results: shell syntax pass, targeted MTP tests pass, manual exporter pass,
no-signoff MTP script exits before prompt export/GPU work with code `3`, compile
pass, `git diff --check` pass with CRLF warnings only, policy `PASS`, and full
unittest pass (`263` tests).

Suggested next command after owner sign-off on a GPU pod:

```bash
OWNER_SIGNOFF=1 \
BENCH_INPUT_PATH=/workspace/bang_c/tests/fixtures/multilingual_gold.json \
BENCH_PROMPT_SELECTION=longest \
BENCH_PROMPT_MODE=reasoning \
bash /workspace/bang_c/scripts/gpu/run_mtp_server.sh
```

For a real contest-shaped measurement, replace `BENCH_INPUT_PATH` with the
mounted evaluation input path available on the pod. Pull the full
`/workspace/mtp_server_logs/` directory before terminating the pod.
