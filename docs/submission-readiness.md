# Bang C Submission Readiness

Status: active
Last updated: 2026-06-18

> **⚠️ CẬP NHẬT 2026-06-18 — bài nộp đã đổi sang ≤5B.** BTC chuyển luật sang **≤5B tham số**, nên mô
> hình Gemma-4-26B (mô tả bên dưới, lịch sử) **không còn hợp lệ**. Bài nộp hiện tại = **Qwen3-4B-Instruct-2507**
> trong image `hacamy12345/neko-core:qwen3-4b-selfconsist-20260618` = `:v0.7.2` = `:latest` (digest
> `sha256:39c7891c…575eaf`, 17.62GB, CUDA arch sm_70/75/80/86/89/90/120 + PTX floor compute_60 → mọi GPU NVIDIA), public-463 = **83.59**.
> Hợp đồng I/O + cách reproduce: **`README.md`** là nguồn chính. Mục bên dưới giữ để tham chiếu lịch sử.
>
> **✅ RÀ SOÁT CUỐI + KHÓA (2026-06-18):** đã verify đầy đủ contract BTC — (1) cả 3 tag trên Docker Hub
> (`:qwen3-4b-selfconsist-20260618` = `:v0.7.2` = `:latest`) cùng resolve về digest `sha256:39c7891c…575eaf`,
> khớp README/Dockerfile; (2) `Dockerfile.qwen-selfconsist.kaniko` bake đúng Qwen3-4B-Instruct-2507 Q5_K_M
> (dense 4B ≤5B), ENV `local_llamacpp`, KHÔNG bật `NEKO_LOCAL_SERVER_MODE` → nhánh MTP Gemma-26B trong
> entrypoint là dead-code (không bao giờ chạy, không vi phạm ≤5B); (3) ENTRYPOINT/CMD đọc `/data` → ghi
> `/output/pred.csv (qid,answer)`, offline, no API; (4) policy overlay ép `max_params_b=5.0`; (5) arch
> sm_70–120 (+PTX compute_60) + `GGML_NATIVE=off` (mọi GPU/CPU judge). **Bài nộp v0.7.2 ĐÃ KHÓA, không cần đổi gì.**
>
> **✅ LITERAL SMOKE-TEST (2026-06-18):** kéo nguyên image v0.7.2 từ Docker Hub (crane export đủ 38 layer) trên
> 1 GPU sạch → `cuobjdump libggml-cuda.so` xác nhận native SASS `sm_60/70/75/80/86/89/90/120` (P100→Blackwell,
> gồm **sm_70 V100**) → chroot chạy entrypoint thật trên test CSV (rc=0, ~30s) → `pred.csv` hợp lệ `qid,answer`.
> Pull + model + arch + chạy end-to-end đều PASS — bài nộp đã kiểm chứng literal trên máy sạch.
> Fine-tune đã thử (v1/v2) → không thắng base, không ship: `notes/2026-06-18-finetune-verdict.md`.

## Vòng-1 deliverables checklist (per the official rules — "Yêu cầu đầu ra")

The contest rules require ALL of the following for Bảng C, submitted **within 72h of the
Vòng-1 leaderboard close** (registration window 02/6–23/6/2026; the final tuned Docker for
Vòng-2 scoring is due 26/6/2026). Missing the deadline = automatic disqualification.

| # | Deliverable (rule wording) | Where / status |
|---|---|---|
| 1 | **Docker Container** on Docker Hub — reads `/data/*_test.csv`, writes `/output/pred.csv` (`qid,answer`) | `hacamy12345/neko-core:gemma26b-q4-portable-20260614` (v0.6.0, clean rebuild, no hard-codes; `llama-cpp-python` source-built `GGML_NATIVE=off` → runs on any CPU; digest sha256:5d264f5d…); self-contained, offline. Outputs identical to the prior `…-clean-20260614` (88.34 leaderboard). |
| 2 | **GitHub** repo with code + how to reproduce the result in the container | this repo; reproduce steps in `README.md` (top "Reproduce" section) + below |
| 3 | **Tài liệu thuyết minh phương pháp** (free format; best shows creativity + effectiveness of the optimization strategy) | `docs/method-writeup-vi.md` (VI, the scored Idea doc) + `docs/method-writeup.md` (EN) |

Vòng-2 scoring (private 2000q): Accuracy 80đ · Time 10đ · Ý tưởng 10đ. The shipped run is
Gemma-4-26B-A4B QAT-Q4_0, self-consistency CoT (k=1, 2048 tokens) + safety-refusal +
constrained-repair + bulletproof contract-repair. Public-463 leaderboard **88.34** (clean
v0.6.0 rebuild; the prior 88.55 is the same path within ±1-question build noise). 227 unit
tests green. (Pre-final hardening TODO: build llama-cpp-python with `GGML_NATIVE=OFF` so the
image cannot SIGILL on an old-CPU judge machine; MTP/local_server deferred — chat-template
divergence from the in-process path not yet at accuracy parity.)

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
