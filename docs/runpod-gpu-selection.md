# RunPod GPU Selection

Status: active guidance
Last updated: 2026-06-10

## Purpose

Use RunPod only as development infrastructure for building and profiling the
local Gemma image. The Bang C scoring path should still be self-contained:

```text
/data/public_test.csv or /data/private_test.csv
  -> local Gemma 4 26B A4B QAT Q4_0 GGUF
  -> /output/pred.csv
```

RunPod API keys, NVIDIA keys, Hugging Face tokens, and pod-specific settings
must stay outside git.

For pod lifecycle, stop-vs-terminate cost, setup, artifact copy-out, and the
recommended laptop-baseline-to-RunPod workflow, see
`docs/runpod-operations.md`.

## BTC-Local Parity Principle

RunPod is useful only when it simulates the same path BTC will run:

```text
docker image containing Neko Core + local GGUF model
mounted /data input
mounted /output output
no NVIDIA_API_KEY
no web access required by the solver
no Wiii/backend/database/browser dependency
```

The lightweight API image is not the submission runtime. It is acceptable for
development, but a BTC-parity test must run the `Dockerfile.gemma-local` image
with `local_llamacpp`.

Current acceptance criteria for the RunPod research loop:

1. Create a GPU pod with a CUDA-capable base environment.
2. Build or pull the self-contained Gemma-local image.
3. Run `neko --doctor` inside the final image and confirm:
   `profile=gemma26b-q4-local`, `provider=local_llamacpp`, model file found.
4. Run a contest-style command with `/data` and `/output`.
5. Confirm `/output/pred.csv` has exact `qid,answer` columns.
6. Stop or terminate the pod when the test window ends.

This keeps the experiment honest: if a run works only through NVIDIA API or
host-local files outside the image, it is not BTC-equivalent.

Current image status:

```text
host-level local Gemma full public run: PASS, 463/463 predictions
self-contained Docker image build/push: PASS
direct RunPod launch from image digest: PASS
final-image contract smoke: PASS, 1 row through /data -> /output/pred.csv
full 463-row run from the final image: pending budgeted confirmation
```

Pinned image for follow-up runs:

```text
hacamy12345/neko-core:gemma26b-q4
hacamy12345/neko-core:gemma26b-q4-20260610
hacamy12345/neko-core@sha256:7034f3a4da3d00bc2de8d7d5ea56422cdeb5e74651a90beba220a962dc0f6760
```

## Current Snapshot

The RunPod account queried after the 2026-06-10 image smoke reported:

```text
balance: 2.044 USD
current spend/hr: 0
```

Relevant candidates from the live GPU inventory:

| GPU | VRAM | Best observed price | Approx hours at 2.044 USD | Notes |
| --- | ---: | ---: | ---: | --- |
| RTX A6000 | 48 GB | 0.33 USD/hr | 6.19 h | Best default development choice: enough VRAM, good value, broad availability. |
| A40 | 48 GB | 0.44 USD/hr | 4.65 h | Good fallback when A6000 is unavailable; cheaper community price may appear but should not be assumed available. |
| L40S | 48 GB | 0.79 USD/hr | 2.59 h | Faster choice when wall-clock time matters more than budget. |
| A100 PCIe | 80 GB | 1.19 USD/hr | 1.72 h | Useful for short high-throughput profiling. |
| H100 PCIe | 80 GB | 1.99 USD/hr | 1.03 h | Fast, but current balance leaves too little margin for image build and download. |
| RTX 4090 | 24 GB | 0.34 USD/hr | 6.01 h | Fast value card, but 24 GB is tight for 26B Q4 plus 8K context and overhead. |

Some very cheap high-memory entries may appear in the API, but do not make them
the default until availability and driver/runtime fit are verified. In
particular, AMD GPUs are not the first target for the current `llama.cpp` CUDA
path, and community/spot fields can look attractive without enough available
capacity.

## Recommendation

Default for current development:

```text
RTX A6000 48 GB community
```

Fallback:

```text
A40 48 GB secure/community when actually available
```

Speed-up profile after topping up or for short runs:

```text
L40S 48 GB, then A100/H100 only for measured profiling
```

Do not start with RTX 4090 unless the goal is a quick experiment and the run can
tolerate CPU offload or lower context. It is not the safest default for the
self-contained Gemma 26B Q4 contest image.

## Repeatable Shortlist Command

Set the key outside git:

```powershell
$env:RUNPOD_API_KEY = "<set outside git>"
.\scripts\runpod-gpu-shortlist.ps1 -MinMemoryGB 48
```

Machine-readable output:

```powershell
.\scripts\runpod-gpu-shortlist.ps1 -MinMemoryGB 48 -Json
```

The script is read-only. It calls RunPod GraphQL metadata, prints balance and
candidate GPU prices, and does not create pods or spend money.

RunPod's documented GraphQL pod operations are `podFindAndDeployOnDemand` for
creation, `podStop` for releasing the GPU while preserving volume data, and
`gpuTypes`/`lowestPrice` for availability checks. Prefer stock-aware creation:
query stock first, try RTX A6000, then A40/L40S only if needed.

## Build Implication

The local Gemma image must use a CUDA-capable `llama-cpp-python` install when it
is built for RunPod/GPU profiling. The default build script passes a CUDA wheel
index:

```powershell
.\scripts\build-gemma-image.ps1 -Image <dockerhub-user>/neko-core:gemma26b-q4
```

For CPU-only debugging:

```powershell
.\scripts\build-gemma-image.ps1 -Image neko-core:gemma-cpu-debug -CpuOnly
```

Keep the final artifact reproducible: record GPU type, image tag, config
profile, input hash, and run report path for every serious benchmark.

## 2026-06-10 A40 Parity Run

RunPod was used to validate the local Gemma runtime path with a real GPU:

```text
pod purpose: neko-core-gemma26b-parity
GPU: NVIDIA A40
VRAM: 46068 MiB
driver: 570.195.03
price observed: 0.44 USD/hr
account balance after termination: about 3.070 USD
current spend/hr after termination: 0
runtime profile: gemma26b-q4-local
provider: local_llamacpp
model: google/gemma-4-26B-A4B-it-qat-q4_0-gguf:Q4_0
model path: /models/gemma-4-26B_q4_0-it.gguf
```

Validated results:

```text
unit tests: 74/74 passed on RunPod Linux
doctor: local model found
public test: 463/463 predictions
workflow: contest-strict
elapsed wall time: about 5 minutes 13 seconds
fallbacks: 0
submission check: valid, no issues
output contract: /output/pred.csv with qid,answer
local artifact copy: E:\Sach\Sua\_tmp\neko-core-runpod-a40-20260610
```

Trace review produced four WARN findings:

```text
test_0009, test_0070, test_0225, test_0440
```

Those four qids were rerun with the `tournament` workflow and all answers stayed
the same as the full run. Treat the warnings as reviewer-attention signals, not
as contract failures.

Docker parity status from the first A40 host-level run:

```text
host-level local Gemma runtime: PASS
final Docker image build inside this RunPod pod: BLOCKED
reason: nested Docker is not permitted by the pod container; dockerd fails on
mount/unshare permissions even with iptables disabled.
```

This was resolved later on 2026-06-10 by using Kaniko on a larger RTX A6000
builder and then launching an A40 pod directly from the pushed image digest. See
`docs/runpod-operations.md` for the pinned image, digest, and Kaniko lessons.

If the image must be rebuilt, use one of these environments:

1. a machine with a real Docker daemon and NVIDIA container runtime;
2. a privileged build pod/template that supports Docker-in-Docker;
3. an external image builder such as CI or a registry builder, followed by a
   RunPod pod launched directly from the built image.

The local Windows Docker Desktop path was not used for the Gemma image during
this run because the Docker storage drive had too little free space for a
large model-containing image. Avoid pruning unrelated local Docker data without
maintainer approval.
