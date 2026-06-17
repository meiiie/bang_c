# Neko Core

[![CI](https://github.com/meiiie/bang_c/actions/workflows/ci.yml/badge.svg)](https://github.com/meiiie/bang_c/actions/workflows/ci.yml)
[![Release](https://github.com/meiiie/bang_c/actions/workflows/release.yml/badge.svg)](https://github.com/meiiie/bang_c/actions/workflows/release.yml)

![Neko Core banner](docs/assets/neko-core-banner.png)

Trạng thái: bài dự thi **HackAIthon 2026 — Bảng C (Innovator)**

**Neko Core** là một harness suy luận *config-first*, đóng gói thành **một Docker image offline,
tự chứa**: đọc đề trắc nghiệm tại `/data`, chạy mô hình **Qwen3-4B-Instruct-2507 (GGUF, dense ≤5B)**
ngay trong container, rồi ghi kết quả ra `/output/pred.csv`. Không cần API key, không cần mạng — đúng
"Yêu cầu đầu ra" của Bảng C.

> **Cập nhật quy tắc 2026-06-16:** Ban Tổ chức chuyển sang **giới hạn ≤5B tham số, mở lựa chọn mô
> hình**. Mô hình thi đấu vì vậy là **Qwen3-4B-Instruct-2507** (dense 4B, ≤5B rõ ràng), thay cho
> Gemma-4-26B trước đây (26B > 5B). Allowlist mô hình giờ là **config-driven** (`runtime.model_policy`
> trong `configs/default.json`) — đổi luật chỉ là sửa dữ liệu, không sửa code.

## Tuân thủ yêu cầu đầu ra Bảng C (checklist)

| Yêu cầu BTC | Đáp ứng |
|---|---|
| **Docker Container trên Docker Hub** | ✅ `hacamy12345/neko-core:qwen3-4b-selfconsist-20260616` (= `:v0.7.1` = `:latest`, digest `sha256:e9aada9b…011c`, ~17.36GB) |
| **Entry-point đọc `public_test.csv` / `private_test.csv` tại `/data`** | ✅ tự nhận diện theo `contest.input_candidates` (ưu tiên `private_test.csv` → `public_test.csv` → biến thể `.json`); đọc CSV bằng `csv.DictReader` (hỗ trợ BOM). **Đã smoke-test trên GPU** với `public_test.csv` |
| **Ghi `pred.csv` vào `/output` với hai cột `qid,answer`** | ✅ ghi-trước-khi-validate, đủ mọi `qid`, mỗi `answer` là 1 chữ cái A–J hợp lệ theo số phương án từng câu |
| **GitHub chứa code + cách reproduce** | ✅ [github.com/meiiie/bang_c](https://github.com/meiiie/bang_c) — mã nguồn + `Dockerfile.qwen-selfconsist.kaniko` + hướng dẫn `docker run` (dưới) |
| **Mô hình ≤5B, một mô hình, không mô hình/API ngoài** | ✅ Qwen3-4B-Instruct-2507 (dense 4B GGUF), chạy `local_llamacpp` offline, một mô hình duy nhất |
| **Thuyết minh phương pháp (Ý tưởng)** | ✅ [`docs/method-writeup-vi.md`](docs/method-writeup-vi.md) + PPTX nộp riêng |

## Đội thi — Neko Core

Trường **Đại học Hàng hải Việt Nam (VMU)**.

| Họ và tên | Lớp | Vai trò |
|---|---|---|
| Nguyễn Mạnh Hùng | CNT63ĐH | **Trưởng nhóm** (Team lead) |
| Bùi Việt Hoàng | CLC63ĐH | Thành viên |
| Phạm Thị Minh Hồng | CNT63ĐH | Thành viên |
| Phạm Thị Thu Thảo | KTN63ĐH | Thành viên |
| Nghiêm Thị Mỹ Linh | KPM63ĐH | Thành viên |

## Cách tái lập kết quả trong container (Ban Tổ chức đọc phần này)

Bài nộp là **một Docker image offline duy nhất, đã nướng sẵn mô hình bên trong**.

**Yêu cầu môi trường:**

| | |
|---|---|
| GPU | **NVIDIA** (≥ 6GB VRAM; image dùng ~5GB) + driver hợp CUDA 12.8. Wheel nướng native SASS cho **sm_75/80/86/89/90/120** → chạy **T4, A100, H100, Ampere, Ada, Blackwell** (đã verify `cuobjdump` trên image đã push) |
| Docker | Docker Engine/Desktop + **NVIDIA Container Toolkit** (cho cờ `--gpus all`) |
| Dung lượng | ~20GB trống (image ~17GB nén) |
| Mạng | chỉ cần lúc `docker pull`; **lúc chạy hoàn toàn offline** |
| OS | Linux/macOS (khuyến nghị) hoặc Windows (Docker Desktop + WSL2) |

**Linux / macOS (bash):**

```bash
# 1) Kéo image (mô hình ≤5B nướng sẵn; ~17GB nén — phần lớn là base CUDA PyTorch)
docker pull hacamy12345/neko-core:qwen3-4b-selfconsist-20260616

# 2) Đặt đề thi vào ./data rồi chạy
mkdir -p data output
cp private_test.csv data/                       # (hoặc public_test.csv)
docker run --rm --gpus all \
  -v "$PWD/data:/data" -v "$PWD/output:/output" \
  hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
# => ./output/pred.csv   (hai cột: qid,answer)
```

**Windows (PowerShell)** — chỉ khác cách viết đường dẫn mount:

```powershell
docker pull hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
mkdir data, output -Force
copy private_test.csv data\
docker run --rm --gpus all `
  -v "${PWD}\data:/data" -v "${PWD}\output:/output" `
  hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
```

Container tự động dò file đề trong `/data` (thứ tự `private_test.csv` → `public_test.csv` → biến thể
`.json`), chạy workflow mặc định `self-consistency`, và ghi `/output/pred.csv`. `pred.csv` được **ghi
TRƯỚC khi kiểm tra hợp đồng** và tự khớp đúng tập `qid` đầu vào, nên một câu lỗi không bao giờ làm hỏng
(về 0) cả lần chạy. Mọi thứ chạy **offline** — không web, không API key, không dịch vụ ngoài.

> Image **dựng sạch từ chính commit này** (`Dockerfile.qwen-selfconsist.kaniko`), không gắn cứng đáp án
> public-test trong bất kỳ layer nào. Runtime `llama-cpp-python` build nguồn `GGML_NATIVE=off` → **chạy
> trên mọi CPU** (wheel prebuilt SIGILL trên CPU cũ). Mô hình nướng sẵn: `Qwen3-4B-Instruct-2507` Q5_K_M
> GGUF. Workflow `self-consistency` được chọn vì **robust > 1pp accuracy** — rủi ro thật của Bảng C là
> container về 0 điểm (OOM/timeout/crash), không phải sai vài câu; RAG và LoRA fine-tune để ở image kế tiếp.
>
> _(Image cũ `gemma26b-q4-portable-20260614` đạt 88.98 trên public-463 nhưng dùng mô hình 26B — **không
> còn hợp lệ** dưới luật ≤5B; giữ chỉ để tham chiếu lịch sử.)_

### Hợp đồng đầu vào / đầu ra

| Hạng mục | Giá trị |
|---|---|
| File đầu vào | `/data/private_test.csv` (hoặc `public_test.csv`; cũng nhận `.json`) |
| Cột đầu vào | `qid`, `question`, và phương án — **một trong hai**: cột `choices` (danh sách JSON, hoặc ngăn bằng `\|\|\|`/tab), **hoặc** các cột chữ cái `A,B,C,D,…` |
| File đầu ra | `/output/pred.csv` |
| Cột đầu ra | `qid,answer` |
| Giá trị `answer` | một chữ cái theo số phương án của TỪNG câu (A, B, C, D… tới J cho câu nhiều lựa chọn) |

Loader đọc CSV bằng `csv.DictReader` (chịu BOM) và nhận tên cột không phân biệt hoa/thường; xem
`contest.input_candidates` trong `configs/default.json` cho thứ tự dò file.

### Tự kiểm thử nhanh (chạy đúng trên máy bất kỳ?)

Để xác nhận container chạy đúng trên **một máy khác** mà chưa có đề thật, tạo một file mẫu rồi chạy y
hệt lệnh trên. Lưu thành `data/private_test.csv`:

```csv
qid,question,A,B,C,D
demo_001,"2 + 2 = ?",3,4,5,6
demo_002,"Thủ đô của Việt Nam là?",Hà Nội,Huế,Đà Nẵng,TP. Hồ Chí Minh
```

```bash
docker run --rm --gpus all -v "$PWD/data:/data" -v "$PWD/output:/output" \
  hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
cat output/pred.csv
# Kỳ vọng:
#   qid,answer
#   demo_001,B
#   demo_002,A
```

Nếu ra đúng `pred.csv` hai cột `qid,answer` với đáp án A–D → pipeline chạy chuẩn trên máy đó. (Máy
không có GPU vẫn chạy được nhưng RẤT chậm — bỏ `--gpus all` để thử CPU với file mẫu nhỏ; bộ 2000 câu
thì bắt buộc GPU.)

### Chạy trên private test 2000 câu (Vòng-2)

Lệnh **giống hệt** phần trên — chỉ cần đặt `private_test.csv` vào `./data`:

```bash
mkdir -p data output
cp private_test.csv data/
docker run --rm --gpus all -v "$PWD/data:/data" -v "$PWD/output:/output" \
  hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
# => ./output/pred.csv  (2000 dòng: qid,answer)
```

- **Tự ưu tiên `private_test.csv`** (đứng đầu `contest.input_candidates`) nên không cần đổi cấu hình.
- **Thời gian:** ~3 giây/câu trên 1 GPU (đo trên 463 = 1336s) → 2000 câu ≈ **~100 phút**. Một mô hình
  4B, VRAM thấp (~5GB) — **không OOM** trên mọi GPU thi đấu.
- **Chống về 0 điểm:** `--checkpoint-every 1` + `--auto-resume` (ghi sau mỗi câu); nếu container bị
  ngắt giữa chừng, chạy lại sẽ tiếp tục từ checkpoint thay vì làm lại từ đầu. `pred.csv` được ghi
  TRƯỚC khi validate và tự khớp đúng tập `qid` → một câu lỗi không bao giờ làm hỏng cả lần chạy.

### Chi tiết image (đã nướng sẵn)

| | |
|---|---|
| Tag (3 tag, cùng 1 digest) | `:qwen3-4b-selfconsist-20260616` = `:v0.7.1` = `:latest` |
| Digest | `sha256:e9aada9bdc43a97ce2f28ba604ddb261a2175ed66ddd72790ead4a304fad011c` |
| Kích thước | ~17.36GB nén (base CUDA PyTorch chiếm phần lớn; model chỉ ~2.7GB) |
| Phiên bản | Neko Core **v0.7.1** (arch-portable: mọi GPU NVIDIA) |
| Mô hình nướng sẵn | `Qwen3-4B-Instruct-2507` Q5_K_M GGUF tại `/models/qwen3-4b.gguf` |
| Runtime | `llama-cpp-python` build nguồn `GGML_NATIVE=off` (mọi CPU) + CUDA native SASS sm_75/80/86/89/90/120 (mọi GPU NVIDIA: T4→A100→H100→Blackwell) |
| Metadata | OCI labels (`docker inspect` xem `org.opencontainers.image.*` + `neko.model/workflow/contest` + `neko.cuda_arch`) |

> Cả ba tag (`:qwen3-4b-selfconsist-20260616`, `:v0.7.1`, `:latest`) đều trỏ cùng digest `e9aada9b…011c`
> = image ≤5B Qwen3-4B v0.7.1. Tag có ngày là canonical (bất biến) — nên pin nó khi nộp.

### Mô hình & tuân thủ quy tắc Bảng C

- LLM: **Qwen3-4B-Instruct-2507** (dense 4B, GGUF Q5_K_M), chạy local qua llama.cpp (offline). Tuân
  thủ luật Bảng C mới (2026-06-16): **≤5B tham số, mở mô hình, một mô hình duy nhất, không mô hình/API
  ngoài**. Allowlist là **config-driven** (`runtime.model_policy`): `{"aliases":["*"],"max_params_b":5.0}`
  ép mọi mô hình ≤5B; cờ `count_active_for_moe` để chốt total-vs-active cho MoE nếu cần.
- **Không gắn cứng đáp án public-test**; mọi đòn bẩy phải tổng quát hoá cho bộ private 2000 câu.

### Kết quả đã đo (minh bạch)

- **Public-463 leaderboard: 83.59** — Qwen3-4B self-consistency, đo thật trên leaderboard chính thức.
  Đây là bản ≤5B **chưa fine-tune, chưa RAG** (sàn an toàn). Đường tăng điểm tiếp theo: fine-tune
  (LoRA) + RAG có kiểm soát — xem [`docs/method-writeup-vi.md`](docs/method-writeup-vi.md).
- **Hợp đồng đầu ra:** mỗi lần chạy harness tự kiểm `valid=True` + ghi `pred.csv` đủ mọi `qid`, đúng
  hai cột, mỗi đáp án là chữ cái A–J hợp lệ theo số phương án của TỪNG câu (49/463 câu có > 4 phương án).
  Container đọc CSV (`csv.DictReader`, hỗ trợ BOM) **và** JSON; thứ tự tìm: `private_test.csv` →
  `public_test.csv` → `private_test.json` → `public_test.json` (`contest.input_candidates`).
- **Đã smoke-test đường CSV (GPU, 2026-06-16):** chạy ship config trên `public_test.csv` (đúng format
  BTC) → `pred.csv` hợp lệ (463 dòng, 0 fallback, contract 40/40) và **trùng khớp 463/463 (100%)** với
  bản pred JSON đã đạt 83.59 → loader đọc CSV BTC cho ra đúng đáp án ghi điểm.

### Tài liệu thuyết minh phương pháp (chấm điểm Ý tưởng)

- [`docs/method-writeup-vi.md`](docs/method-writeup-vi.md) — **Tiếng Việt** (bản chi tiết)
- [`docs/method-writeup.md`](docs/method-writeup.md) — English

> Bản trình bày **PPTX** được nộp riêng theo kênh của Ban Tổ chức.

---

## Developer reference (English)

Neko Core is a **config-first** harness: model/provider selection, thresholds, and rubric weights
live in `configs/default.json`, not in source. The submitted container is intentionally minimal and
offline; development tracing/eval lives outside the shipped artifact.

### Project structure

```text
src/hackaithon_c/      Harness: loader -> classifier -> prompting -> solver -> normalizer
                       -> contract validation -> pred.csv exporter (+ config, calibration, checkpoint)
configs/default.json   Config-first runtime: providers, model paths, profiles, thresholds, rubric,
                       runtime.model_policy (the config-driven ≤5B model allowlist)
docker/                neko-entrypoint.sh (reads /data, writes /output/pred.csv)
                       + qwen-selfconsist.neko-core.json (the baked ≤5B image config overlay)
Dockerfile.qwen-selfconsist.kaniko   The ≤5B contest image build (Kaniko, self-contained Qwen3-4B Q5_K_M)
scripts/               Build + dev helpers
tests/                 Unit tests (run: python -m unittest discover -s tests)
docs/                  Method write-up, architecture, evaluation rubric
notes/                 Measured-result analysis (the leaders + the rejected levers, with numbers)
```

### Run locally (development)

```powershell
.\scripts\bootstrap.ps1          # create .venv, install editable package, fast checks
.\neko.ps1 --doctor              # environment + contract diagnostics
.\neko.ps1 --workflow self-consistency --input <public-test.json> --run-dir run --auto-resume
.\neko.ps1 --check-submission <pred.csv>   # validate name/header/qids/per-row letters
```

`--check-submission` derives the valid answer letters per row from the input (no hard-coded A–D).
NVIDIA is an optional **development-only** provider (`--profile nvidia-gemma31b-api` + `NVIDIA_API_KEY`);
the contest path stays `local_llamacpp` with the baked GGUF.

### Build the contest image (reproducibility)

The submitted image is built from this commit by `Dockerfile.qwen-selfconsist.kaniko` — it source-builds
`llama-cpp-python` with `GGML_NATIVE=OFF` (so the binary runs on any judge CPU) and bakes
`Qwen3-4B-Instruct-2507` Q5_K_M GGUF + the harness + the `docker/qwen-selfconsist.neko-core.json` config
overlay. No public-test answers are baked into any layer.

```bash
# Build + push (Kaniko, no Docker-in-Docker needed; or use `docker build` on a Docker host):
/kaniko/executor \
  --context dir://. \
  --dockerfile ./Dockerfile.qwen-selfconsist.kaniko \
  --destination docker.io/hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
```

The image is large (~17GB compressed — the CUDA PyTorch base dominates; the model is only ~2.7GB).
See [`docs/runpod-operations.md`](docs/runpod-operations.md) and [`docs/release-process.md`](docs/release-process.md).

### Architecture & docs

- [`docs/AGENTIC-CLI-DEVELOPER-GUIDE.md`](docs/AGENTIC-CLI-DEVELOPER-GUIDE.md) — **deep guide** for
  developing Neko Core as a reusable AI Agentic CLI (providers/API setup, env vars, workflows,
  agent/tool registries, how to extend). Read this to build on Neko Core beyond the contest.
- [`docs/harness-architecture.md`](docs/harness-architecture.md) — layered pipeline + contracts
- [`docs/evaluation-rubric.md`](docs/evaluation-rubric.md) — scoring model
- [`docs/local-gemma-runtime.md`](docs/local-gemma-runtime.md) — local llama.cpp GGUF runtime mechanics
  (written for Gemma; the same `local_llamacpp` path now serves the ≤5B Qwen3-4B GGUF)
- [`notes/2026-06-16-le5b-rules-and-model-policy.md`](notes/2026-06-16-le5b-rules-and-model-policy.md) —
  the ≤5B rules pivot, config-driven model policy, and measured Qwen3-4B results
- [`docs/submission-readiness.md`](docs/submission-readiness.md) — submission checklist
