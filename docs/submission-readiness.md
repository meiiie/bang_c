# Bang C Submission Readiness

Status: active
Last updated: 2026-06-10

## Required Runtime Contract

The organizer-facing contract is intentionally narrow:

```text
/data/public_test.csv or /data/private_test.csv
  -> Docker entrypoint
  -> /output/pred.csv
```

`pred.csv` must contain exactly two columns:

```csv
qid,answer
```

## Website Upload Note

On 2026-06-09, the website accepted the corrected artifact only after we used a
file named `pred.csv` with the exact runtime contract. The older downloaded
sample/upload artifact was misleading for this development corpus and should
not be treated as the source of truth for file naming, encoding, or global
answer alphabet.

Use the official rules and runtime contract as the source of truth:

- file name: `pred.csv`;
- columns: `qid,answer`;
- row count and qids must match the provided input;
- valid answer letters come from each row's choices, not from a global A-D
  assumption.

The harness must not assume a global A-D answer alphabet. The valid answer
letters come from the options present in each input row. If a row has A-J
choices, an E/J answer can be valid for that row. The submission checker
validates this from the input file rather than hard-coding a fixed alphabet.

## Current Neko Core Status

Implemented:

- Docker entrypoint: `python -m hackaithon_c.run`.
- Default Docker command reads `/data`, writes `/output/pred.csv`, and stores
  checkpoint/review artifacts under `/output/neko-run`.
- Default harness provider is `local_llamacpp` with
  `google/gemma-4-26B-A4B-it-qat-q4_0-gguf:Q4_0`.
- `Dockerfile.gemma-local` builds a self-contained Gemma image by downloading
  `gemma-4-26B_q4_0-it.gguf` into `/models`.
- `Dockerfile.gemma-local.kaniko` builds the same self-contained image on
  RunPod without Docker-in-Docker.
- The lightweight `Dockerfile` is an API/development image and sets
  `HACKC_PROVIDER=nvidia`; it is not the preferred BTC scoring image.
- Config input candidates prefer `private_test.csv` and `public_test.csv`
  before local JSON compatibility files.
- Exporter writes UTF-8 CSV with exact `qid,answer` columns.
- `--yolo` provides a bounded autonomous run preset with `contest-strict`,
  auto-resume, checkpointing, policy enforcement, and review artifacts.
- `--check-submission` validates the final `pred.csv` name, header, qids,
  row count, duplicates, and per-row answer alphabet.

Published local Gemma image:

```text
hacamy12345/neko-core:gemma26b-q4
hacamy12345/neko-core:gemma26b-q4-20260610
hacamy12345/neko-core@sha256:7034f3a4da3d00bc2de8d7d5ea56422cdeb5e74651a90beba220a962dc0f6760
```

Validated:

- host-level RunPod A40 local Gemma full public run: 463/463 predictions,
  valid `/output/pred.csv`;
- direct RunPod A40 launch from the pushed image digest: model file present,
  doctor pass, 1-row `/data -> /output/pred.csv` contract smoke pass.

Still worth doing before final Docker-based submission:

- Run the full 463-row public file from the pushed image once more. The runtime
  is already proven at host level and the image contract smoke passed, but a
  final full-image run removes the last packaging doubt.
- Public website upload is still manual unless the organizer accepts the Docker
  Hub image plus GitHub repo directly.
- A clean official `public_test.csv` file should be used for the final dry run;
  older local JSON files are development compatibility artifacts.

## How BTC Is Expected To Run It

The likely organizer run flow is:

```bash
docker pull <dockerhub-user>/neko-core:<tag>
mkdir -p data output
cp private_test.csv data/private_test.csv
docker run --rm \
  -v "$PWD/data:/data" \
  -v "$PWD/output:/output" \
  <dockerhub-user>/neko-core:<tag>
test -f output/pred.csv
```

The container should finish with:

```text
/output/pred.csv
```

No extra command should be required. The default `CMD` already selects the
strict contest workflow and writes `pred.csv` to `/output`.

## Local Verification

Run a Docker contract smoke with a CSV fixture:

```powershell
docker build -t neko-core:dev .
mkdir data-smoke, output-smoke
@"
qid,question,A,B,C,D
sample_001,"Which option is Alpha?",Alpha,Beta,Gamma,Delta
sample_002,"Which option is Delta?",Alpha,Beta,Gamma,Delta
"@ | Set-Content -Path data-smoke\public_test.csv -Encoding utf8
docker run --rm -v "$PWD\data-smoke:/data" -v "$PWD\output-smoke:/output" neko-core:dev --workflow quick-dry-run
.\neko.ps1 --input data-smoke\public_test.csv --check-submission output-smoke\pred.csv
```

For a real public/private run, mount the official CSV and run the default image
command or:

```powershell
.\neko.ps1 core --yolo --input <official-public-or-private-test.csv> --output-dir output --run-dir run-submit
.\neko.ps1 --input <official-public-or-private-test.csv> --check-submission output\pred.csv
```

Upload `output\pred.csv` only.
