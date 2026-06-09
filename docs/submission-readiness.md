# Bang C Submission Readiness

Status: active
Last updated: 2026-06-09

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

The harness must not assume a global A-D answer alphabet. The valid answer
letters come from the options present in each input row. If a row has A-J
choices, an E/J answer can be valid for that row. The submission checker
validates this from the input file rather than hard-coding a fixed alphabet.

## Current Neko Core Status

Implemented:

- Docker entrypoint: `python -m hackaithon_c.run`.
- Default Docker command reads `/data`, writes `/output/pred.csv`, and stores
  checkpoint/review artifacts under `/output/neko-run`.
- Config input candidates prefer `private_test.csv` and `public_test.csv`
  before local JSON compatibility files.
- Exporter writes UTF-8 CSV with exact `qid,answer` columns.
- `--yolo` provides a bounded autonomous run preset with `contest-strict`,
  auto-resume, checkpointing, policy enforcement, and review artifacts.
- `--check-submission` validates the final `pred.csv` name, header, qids,
  row count, duplicates, and per-row answer alphabet.

Not yet complete:

- Docker Hub image is not published until `DOCKERHUB_USERNAME` and
  `DOCKERHUB_TOKEN` repository secrets are configured and a release workflow is
  run.
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
  -e NVIDIA_API_KEY="$NVIDIA_API_KEY" \
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
