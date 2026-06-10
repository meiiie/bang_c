# Local Gemma Runtime Direction

Status: active
Last updated: 2026-06-10

## Decision

Use `Gemma 4 26B A4B QAT Q4_0 GGUF` as the primary Bang C contest runtime.
The final contest image should contain the model weights and should not require
BTC to provide `NVIDIA_API_KEY`.

Chosen model artifact:

```text
repo: google/gemma-4-26B-A4B-it-qat-q4_0-gguf
file: gemma-4-26B_q4_0-it.gguf
runtime id: google/gemma-4-26B-A4B-it-qat-q4_0-gguf:Q4_0
container path: /models/gemma-4-26B_q4_0-it.gguf
```

## Provider Boundary

Neko Core now has two provider modes:

- `local_llamacpp`: default contest path, uses `llama-cpp-python` against a
  local GGUF file.
- `nvidia`: optional development/API path, enabled only with
  `HACKC_PROVIDER=nvidia` and `NVIDIA_API_KEY`.

The solver, verifier, tournament, normalizer, trace writer, and exporter should
not know which provider is active. They only depend on the shared chat-client
contract:

```text
complete(system_prompt, user_prompt, max_tokens) -> text
model -> model identifier
```

The default config exposes those modes through named runtime profiles:

```text
gemma26b-q4-local   -> local_llamacpp, Gemma 4 26B Q4 GGUF
nvidia-gemma31b-api -> nvidia, google/gemma-4-31b-it
```

Use `neko --profiles` to inspect profiles and `neko --profile <name>` or
`HACKC_PROFILE=<name>` to select one. Prefer adding a profile or provider
registry entry over branching inside the solver.

## Build Strategy

Do not commit model files. Do not put `.gguf` files into git.

Build the local Gemma image from a machine with enough disk and network:

```powershell
.\scripts\build-gemma-image.ps1 -Image <dockerhub-user>/neko-core:gemma26b-q4
docker push <dockerhub-user>/neko-core:gemma26b-q4
```

If Hugging Face requires authentication:

```powershell
$env:HF_TOKEN = "<set outside git>"
.\scripts\build-gemma-image.ps1 -Image <dockerhub-user>/neko-core:gemma26b-q4
```

The Dockerfile passes `HF_TOKEN` as a BuildKit secret. It is available only
during model download and is not persisted in the image.

For RunPod/GPU profiling, the build script defaults to a CUDA
`llama-cpp-python` wheel index. For CPU-only debug builds, pass `-CpuOnly`:

```powershell
.\scripts\build-gemma-image.ps1 -Image neko-core:gemma-cpu-debug -CpuOnly
```

## Runtime Contract

The self-contained image must still obey the same narrow contest contract:

```text
/data/public_test.csv or /data/private_test.csv
  -> local Gemma inference
  -> /output/pred.csv
```

No web browsing, Wiii backend, databases, browser automation, subagents,
notebooks, or API keys are allowed in the final scoring path.

## NVIDIA Extension Path

NVIDIA remains useful for:

- quick development when local Gemma is not downloaded yet;
- comparing API model behavior against local Gemma;
- future provider routing or Wiii integration;
- model inventory diagnostics.

Use it explicitly:

```powershell
$env:HACKC_PROVIDER = "nvidia"
$env:NVIDIA_API_KEY = "<set outside git>"
$env:HACKC_LLM_MODEL = "google/gemma-4-31b-it"
.\neko.ps1 --workflow contest-strict --input public_test.csv --run-dir run-nvidia
```

Do not make NVIDIA the implicit contest default unless BTC explicitly changes
the runtime requirement.

## RunPod GPU Direction

Use RunPod only to accelerate development and profiling. The current recommended
GPU is RTX A6000 48 GB community, with A40 48 GB as the fallback and
L40S/A100/H100 reserved for short speed-focused benchmarks.

See `docs/runpod-gpu-selection.md` for the repeatable shortlist command and the
latest selection rationale.

The 2026-06-10 A40 run validated the local Gemma provider against the full
463-row public test in about 5 minutes 13 seconds with no fallbacks and a valid
`/output/pred.csv`. Docker-image parity still needs a true Docker-capable build
environment, because nested Docker inside that RunPod pod was blocked by
container mount/unshare permissions.
