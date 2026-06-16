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

**Yêu cầu:** máy có **GPU NVIDIA** + NVIDIA Container Toolkit (cho cờ `--gpus all`). Image **chạy
trên mọi CPU** (Intel/AMD, có hay không AVX-512) và **hoàn toàn offline** khi chạy.

```bash
# 1) Kéo image (mô hình ≤5B đã nướng sẵn bên trong; ~17GB nén — phần lớn là base CUDA PyTorch)
docker pull hacamy12345/neko-core:qwen3-4b-selfconsist-20260616

# 2) Đặt đề thi vào ./data rồi chạy
mkdir -p data output
cp private_test.csv data/            # (hoặc public_test.csv)

docker run --rm --gpus all \
  -v "$PWD/data:/data" \
  -v "$PWD/output:/output" \
  hacamy12345/neko-core:qwen3-4b-selfconsist-20260616
# => ./output/pred.csv   (hai cột: qid,answer)
```

Container tự động đọc `private_test.csv` (hoặc `public_test.csv`) trong `/data`, chạy workflow mặc định
`self-consistency` (mô hình suy luận từng bước rồi trích ra chữ cái đáp án), và ghi `/output/pred.csv`.
File `pred.csv` được **ghi TRƯỚC khi kiểm tra hợp đồng** và tự sửa cho khớp đúng các `qid` đầu vào,
nên một câu lỗi không bao giờ làm hỏng (về 0) cả lần chạy. Toàn bộ chạy **offline** (không web,
không API key, không phụ thuộc dịch vụ ngoài).

> `qwen3-4b-selfconsist-20260616` được **dựng sạch từ chính commit này** (không có đáp án public-test
> gắn cứng trong bất kỳ layer nào), dùng `Dockerfile.qwen-selfconsist.kaniko`. Runtime `llama-cpp-python`
> build từ nguồn với `GGML_NATIVE=off` nên **chạy trên mọi CPU** (wheel prebuilt SIGILL trên CPU cũ).
> Mô hình nướng sẵn: `Qwen3-4B-Instruct-2507` Q5_K_M GGUF (~2.7GB). Workflow mặc định `self-consistency`,
> chọn robust > 1pp accuracy (rủi ro thật của Bảng C là container về 0 điểm do OOM/timeout/crash, không
> phải sai vài câu) — RAG và LoRA fine-tune được nướng vào image kế tiếp, đo riêng.
>
> _(Image cũ `gemma26b-q4-portable-20260614` đạt 88.34→88.98 trên public-463 nhưng dùng mô hình 26B —
> **không còn hợp lệ** dưới luật ≤5B mới; giữ lại chỉ để tham chiếu lịch sử.)_

### Hợp đồng đầu vào / đầu ra

| Hạng mục | Giá trị |
|---|---|
| Đầu vào | `/data/private_test.csv` (hoặc `/data/public_test.csv`) |
| Đầu ra | `/output/pred.csv` |
| Cột | `qid,answer` |
| Giá trị `answer` | chữ cái phương án theo TỪNG dòng (A, B, C, D… tới J cho câu nhiều lựa chọn) |

### Mô hình & tuân thủ quy tắc Bảng C

- LLM: **Qwen3-4B-Instruct-2507** (dense 4B, GGUF Q5_K_M), chạy local qua llama.cpp (offline). Tuân
  thủ luật Bảng C mới (2026-06-16): **≤5B tham số, mở mô hình, một mô hình duy nhất, không mô hình/API
  ngoài**. Allowlist là **config-driven** (`runtime.model_policy`): `{"aliases":["*"],"max_params_b":5.0}`
  ép mọi mô hình ≤5B; cờ `count_active_for_moe` để chốt total-vs-active cho MoE nếu cần.
- **Không gắn cứng đáp án public-test**; mọi đòn bẩy phải tổng quát hoá cho bộ private 2000 câu.

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
configs/default.json   Config-first runtime: providers, model paths, profiles, thresholds, rubric
docker/                neko-entrypoint.sh (reads /data, writes /output/pred.csv)
Dockerfile.gemma-local.kaniko   The contest image build (Kaniko, self-contained Gemma Q4_0)
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

### Build the contest image

The self-contained Gemma image is large; build it on a machine with enough disk/RAM/network. For
RunPod builders without Docker-in-Docker, `Dockerfile.gemma-local.kaniko` builds it via Kaniko (the
`llama-cpp-python` runtime is source-built with `GGML_NATIVE=OFF` so the image runs on any CPU).
See [`docs/runpod-operations.md`](docs/runpod-operations.md) and [`docs/release-process.md`](docs/release-process.md).

### Architecture & docs

- [`docs/AGENTIC-CLI-DEVELOPER-GUIDE.md`](docs/AGENTIC-CLI-DEVELOPER-GUIDE.md) — **deep guide** for
  developing Neko Core as a reusable AI Agentic CLI (providers/API setup, env vars, workflows,
  agent/tool registries, how to extend). Read this to build on Neko Core beyond the contest.
- [`docs/harness-architecture.md`](docs/harness-architecture.md) — layered pipeline + contracts
- [`docs/evaluation-rubric.md`](docs/evaluation-rubric.md) — scoring model
- [`docs/local-gemma-runtime.md`](docs/local-gemma-runtime.md) — local Gemma runtime
- [`docs/submission-readiness.md`](docs/submission-readiness.md) — submission checklist
