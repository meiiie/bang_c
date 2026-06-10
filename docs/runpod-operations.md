# RunPod Operations Runbook

Status: active guidance
Last updated: 2026-06-10

## Purpose

Use RunPod as disposable acceleration for Neko Core development, not as hidden
contest infrastructure. The contest target remains a self-contained Docker
runtime that reads `/data`, writes `/output/pred.csv`, and does not require
NVIDIA API keys, RunPod state, web access, Wiii, or local notebooks.

RunPod should answer one question at a time:

```text
Does this harness/config change still work with the local Gemma runtime,
quickly enough and accurately enough to justify another submission?
```

## Current Account Snapshot

After the 2026-06-10 image build and direct-image smoke run:

```text
active pods: none
current spend/hr: 0
remaining balance: about 2.044 USD
latest useful GPU: A40 48 GB at 0.44 USD/hr
full 463-row local Gemma run: about 5 minutes 13 seconds
latest final-image smoke: PASS, 1 row through /data -> /output/pred.csv
```

Do not leave a pod stopped "just in case" without a clear reason. Stopped pod
volume storage is still billed.

## Development Strategy

The current direction is correct:

1. Iterate on the laptop with the NVIDIA API profile as the cheap baseline.
2. Run unit tests, contract checks, and small targeted evals locally.
3. Promote only promising changes to RunPod.
4. On RunPod, run the local Gemma profile against the full public test.
5. Copy artifacts back to `E:\Sach\Sua\_tmp\...`.
6. Terminate the pod unless a short-lived stopped environment is worth the
   storage charge.

This separates two problems that should not be mixed:

- answer-quality improvement through prompts, profiling, adjudication, and
  config;
- deployment/runtime proof that `Gemma 4 26B A4B QAT Q4_0 GGUF` works locally
  under the same shape BTC expects.

The leaderboard score of 85.53 means the next work should be systematic error
analysis, not random prompt patching. Use the NVIDIA baseline to explore likely
mistake classes, then use RunPod as the final local-model confirmation.

## Stop vs Terminate

Use these terms precisely:

| Action | GPU charge | `/workspace` volume | Best use |
| --- | --- | --- | --- |
| Stop | GPU released | Kept and billed as stopped volume disk | Resume the same environment soon. |
| Terminate/delete | GPU released | Deleted unless data is on a network volume | End the run and stop all pod-local cost. |

RunPod's published storage rates are:

| Storage type | Running pod | Stopped pod |
| --- | ---: | ---: |
| Container disk | 0.10 USD/GB/month | Not charged; erased when pod stops |
| Volume disk | 0.10 USD/GB/month | 0.20 USD/GB/month |
| Network volume under 1 TB | 0.07 USD/GB/month | 0.07 USD/GB/month |
| Network volume over 1 TB | 0.05 USD/GB/month | 0.05 USD/GB/month |

For the 80 GB pod volume used in the A40 run:

```text
stopped volume estimate: 80 * 0.20 / 30 / 24 = about 0.022 USD/hr
stopped volume per day: about 0.53 USD/day
stopped volume per month: about 16.00 USD/month
network volume under 1 TB: 80 * 0.07 / 30 / 24 = about 0.0078 USD/hr
```

Because the model download and environment setup are now scripted and the full
public run took only about 5 minutes, terminating is normally cheaper than
keeping an 80 GB stopped pod. Stop only when:

- another benchmark will run very soon;
- the pod contains expensive-to-rebuild artifacts not yet copied out;
- a debugging session depends on the exact live environment.

## Repeatable Rental Flow

Set the API key outside git:

```powershell
$env:RUNPOD_API_KEY = "<set outside git>"
```

Check candidates before spending:

```powershell
.\scripts\runpod-gpu-shortlist.ps1 -MinMemoryGB 48
```

Preferred GPUs:

```text
1. RTX A6000 48 GB, if available at a good price
2. A40 48 GB, reliable fallback
3. L40S 48 GB, faster but more expensive
4. A100/H100 only for short speed-focused profiling after top-up
```

Recommended base image for host-level development pods:

```text
runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04
```

Avoid the floating `runpod/pytorch` image for this project unless it is retested.
One earlier attempt exited immediately.

Use:

```text
ports: 22/tcp,8888/http
volumeMountPath: /workspace
startSsh: true
startJupyter: true
terminateAfter: 4h or less for safety
```

## Remote Setup Checklist

Copy the working tree without secrets, outputs, model files, or local caches.
On the pod:

```bash
cd /workspace/neko-core
python -m pip install --upgrade pip
python -m pip install -r requirements-local.txt \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
python -m unittest discover -s tests -v
python -m compileall -q src
```

Prepare paths:

```bash
mkdir -p /workspace/models /workspace/data /workspace/output
ln -sfn /workspace/models /models
ln -sfn /workspace/data /data
ln -sfn /workspace/output /output
```

Download the chosen model only from a permitted source:

```bash
python - <<'PY'
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id="google/gemma-4-26B-A4B-it-qat-q4_0-gguf",
    filename="gemma-4-26B_q4_0-it.gguf",
    local_dir="/workspace/models",
)
PY
```

Run the contest-style full test:

```bash
PYTHONUNBUFFERED=1 PYTHONPATH=src python -m hackaithon_c.run \
  --workflow contest-strict \
  --data-dir /data \
  --output-dir /output \
  --run-dir /output/neko-run-full-local \
  --auto-resume \
  --checkpoint-every 1
```

Validate output before copying:

```bash
PYTHONPATH=src python -m hackaithon_c.run --check-submission \
  --data-dir /data \
  --output-dir /output
```

Required final artifact:

```text
/output/pred.csv
columns: qid,answer
```

## Docker Packaging Result

The first self-contained Gemma image was built and pushed on 2026-06-10:

```text
repository: hacamy12345/neko-core
stable tag: gemma26b-q4
dated tag: gemma26b-q4-20260610
digest: sha256:7034f3a4da3d00bc2de8d7d5ea56422cdeb5e74651a90beba220a962dc0f6760
builder: RunPod RTX A6000 with Kaniko
smoke: RunPod A40 launched directly from the pushed image digest
```

The image contains:

```text
Neko Core
Gemma 4 26B A4B QAT Q4_0 GGUF at /models/gemma-4-26B_q4_0-it.gguf
CUDA llama.cpp Python runtime
default entrypoint that reads /data and writes /output/pred.csv
no NVIDIA API key requirement for the official scoring path
```

Mental model for the team:

```text
RunPod GPU pod = temporary factory used to build/test the large image
Docker Hub = durable registry that stores the pushed image
BTC runner = pulls the image from Docker Hub and mounts /data and /output
```

After the image is pushed to Docker Hub, it no longer depends on the RunPod pod
that built it. Terminating the GPU pod only deletes that temporary machine and
stops billing; it does not delete the Docker Hub image. The image disappears
only if the Docker Hub repository/tag/digest is deleted or overwritten.

The direct-image smoke copied the public test file into `/data` on the pod and
ran:

```bash
cd /app && PYTHONUNBUFFERED=1 PYTHONPATH=/app/src python -m hackaithon_c.run \
  --workflow contest-strict \
  --data-dir /data \
  --output-dir /output \
  --run-dir /output/smoke \
  --limit 1 \
  --auto-resume \
  --checkpoint-every 1
```

Validated output:

```text
/output/pred.csv
qid,answer
test_0001,A
```

Local proof artifacts:

```text
E:\Sach\Sua\_tmp\neko-core-docker-smoke-20260610\
```

This proves the pushed image can start on RunPod with the local model already
inside the image and can satisfy the BTC output contract. It does not replace
the separate full 463-row host-level Gemma run. Before treating the Docker image
as a final submission runtime, run the full public file from the image once more
when budget allows.

## Kaniko Build Lessons

Do not rely on Docker-in-Docker inside the stock RunPod pod. It was blocked by
mount/unshare permissions. The successful path was Kaniko from a large build
pod:

```text
base image: runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04
container disk: 150 GB
volume disk: 160 GB
Dockerfile: Dockerfile.gemma-local.kaniko
```

Keep these details in future runs:

- Use a real `/workspace/kaniko-dir`; do not symlink it into the small Kaniko
  default directory.
- Create `/kaniko` as a real directory if the executor requires it.
- Store Docker auth in `/workspace/kaniko-dir/.docker/config.json`, never in
  git.
- Avoid heredoc-heavy Dockerfile commands for this build path. Kaniko did not
  execute one heredoc model-download block correctly during the first attempt.
  Use `python -c` or a checked-in script and finish with `test -s` on the model
  file.
- 50 GB container disk was not enough after adding the GGUF model layer. Use at
  least the 150 GB/160 GB builder shape above unless the image is redesigned.
- For RunPod smoke on the pushed image, launch with the base image startup
  command if SSH/Jupyter are needed for inspection:

```text
dockerEntrypoint: ["/opt/nvidia/nvidia_entrypoint.sh"]
dockerStartCmd: ["/start.sh"]
```

If overriding the startup this way, set `PYTHONPATH=/app/src` explicitly in
manual smoke commands. For BTC-style execution, do not override the image
entrypoint; let `neko-entrypoint` run with mounted `/data` and `/output`.

## Artifact Discipline

Before stopping or terminating a pod, copy out:

```text
/output/pred.csv
/output/neko-run-full-local/run-report.md
/output/neko-run-full-local/review-tasks.md
selected traces only when needed for debugging
```

Local destination pattern:

```text
E:\Sach\Sua\_tmp\neko-core-runpod-<gpu>-<yyyymmdd>\
```

Never commit:

```text
RunPod API keys
NVIDIA API keys
Hugging Face tokens
model weights
public/private answer files
generated pred.csv
large trace folders
```

## Useful Official References

- RunPod pod lifecycle: https://docs.runpod.io/pods/manage-pods
- RunPod pod pricing: https://docs.runpod.io/pods/pricing
- RunPod GraphQL pod management: https://docs.runpod.io/sdks/graphql/manage-pods
- RunPod GraphQL schema: https://graphql-spec.runpod.io/
