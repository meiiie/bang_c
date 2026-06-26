# Neko Core

[![CI](https://github.com/meiiie/bang_c/actions/workflows/ci.yml/badge.svg)](https://github.com/meiiie/bang_c/actions/workflows/ci.yml)
[![Release](https://github.com/meiiie/bang_c/actions/workflows/release.yml/badge.svg)](https://github.com/meiiie/bang_c/actions/workflows/release.yml)

![Neko Core banner](docs/assets/neko-core-banner.png)

Trạng thái: bài dự thi **HackAIthon 2026 — Bảng C (Innovator) · Vòng 2**

**Neko Core** là một harness suy luận *config-first*, đóng gói thành **một Docker image offline, tự
chứa**. Theo đúng *Submission Guideline* của Ban Tổ chức (BTC) Vòng 2, container:

- **đọc** đề trắc nghiệm tại **`/code/private_test.json`** (BTC mount vào khi chấm),
- chạy mô hình **Qwen3-4B-Instruct-2507 (GGUF Q5_K_M, dense ≤5B)** ngay trong container,
- **ghi** kết quả ra **`/code/submission.csv`** (`qid,answer`) và **`/code/submission_time.csv`**
  (`qid,answer,time` — thời gian suy luận **từng câu**).

Không cần API key, không cần mạng, không mô hình/dịch vụ ngoài. Image build trên **CUDA 12.8** để chạy
được trên GPU chấm của BTC (**NVIDIA RTX 5060 Ti — kiến trúc Blackwell, cần CUDA ≥ 12.8**).

> **Quy tắc ≤5B (2026-06-16):** BTC giới hạn **≤5B tham số, mở lựa chọn mô hình**. Mô hình thi đấu là
> **Qwen3-4B-Instruct-2507** (dense 4B, ≤5B rõ ràng). Allowlist là **config-driven**
> (`runtime.model_policy` trong `configs/default.json`) — đổi luật chỉ là sửa dữ liệu, không sửa code.

---

## Pipeline Flow

```text
  /code/private_test.json                (BTC mount; JSON list: qid, question, choices[])
        │
        ▼
  loader.py        ── đọc JSON/CSV, chuẩn hoá NFC, trích phương án ──► Problem(qid, question, choices)
        │
        ▼
  classifier.py    ── nhận diện dạng câu (reading / calculation / negative / many-choice …)
        │
        ▼
  prompting.py     ── dựng prompt chain-of-thought theo dạng câu (đa ngôn ngữ, trung lập)
        │
        ▼
  solver.py        ── chiến lược "self-consistency" k=1 (1 mẫu CoT/câu) ──► 1 chữ cái đáp án
        │                (đã đo voting k>1 KHÔNG tăng điểm → chốt k=1 để tối ưu Time)
        ▼
  normalize.py     ── trích đáp án nghiêm ngặt (ANSWER: <letter>) + ép về A/B/C/D… hợp lệ
        │
        ▼
  repair (evaluation.py) ── đảm bảo MỌI qid có 1 đáp án hợp lệ (chống-0-điểm)
        │
        ▼
  predict.py       ── đo time.perf_counter() từng câu, ghi 2 file vào /code:
                         submission.csv        (qid,answer)
                         submission_time.csv   (qid,answer,time)
```

Entry-point là **`predict.py`** (gọi qua **`inference.sh`** — `CMD ["bash","/app/inference.sh"]`). Code
nằm ở **`/app`** (KHÔNG ở `/code`) để mount đề của BTC vào `/code` không che mất code. Nó tái dùng nguyên
đường giải đã kiểm thử của harness (`solve_problem` + `repair_predictions_for_contract`), chỉ thêm hợp
đồng I/O của BTC và **đo thời gian từng câu** (vòng `for` theo từng item, dump per-item — không phải trung bình).

## Data Processing

- **Đầu vào** là JSON dạng list, mỗi phần tử `{qid, question, choices[]}` (đúng định dạng public test
  BTC cấp). `loader.py` còn nhận CSV và tên cột không phân biệt hoa/thường.
- **Chuẩn hoá Unicode NFC** cho mọi `question`/`choices` để ổn định suy luận tiếng Việt.
- **Không thu thập / huấn luyện dữ liệu** cho đường nộp này; không gắn cứng đáp án public-test.

## Resource Initialization

- **Mô hình**: tải sẵn **lúc build** từ Hugging Face (`unsloth/Qwen3-4B-Instruct-2507-GGUF`,
  `Qwen3-4B-Instruct-2507-Q5_K_M.gguf`) vào `/models/qwen3-4b.gguf` — **lúc chấm hoàn toàn offline**.
- **Runtime suy luận**: `llama-cpp-python` **build từ nguồn** với **CUDA 12.8** (`GGML_NATIVE=off` để chạy
  trên mọi CPU; **native SASS `sm_120` (Blackwell — đúng RTX 5060 Ti)** + **PTX floor `compute_75`** để
  forward-JIT cho mọi GPU ≥ sm_75 lúc load). KHÔNG cần Vector DB / Indexing / RAG / embedding / rerank.

---

## Tuân thủ Submission Guideline (Vòng 2)

| Yêu cầu BTC | Đáp ứng |
|---|---|
| **Base image CUDA ≥ 12.8** (GPU chấm RTX 5060 Ti / Blackwell) | ✅ `nvidia/cuda:12.8.1-devel-ubuntu22.04` ([`Dockerfile.qwen-submission`](Dockerfile.qwen-submission)) |
| **Entry-point đọc `/code/private_test.json`** | ✅ [`predict.py`](predict.py) (code ở `/app` nên mount `/code` không che) |
| **`inference.sh` chạy pipeline đầu-cuối** | ✅ [`inference.sh`](inference.sh) — `CMD ["bash","/app/inference.sh"]` |
| **Ghi `submission.csv` (`qid,answer`) NGAY trong `/code`** | ✅ ghi-trước-validate, đủ mọi `qid`, mỗi đáp án 1 chữ cái hợp lệ |
| **Ghi `submission_time.csv` (`qid,answer,time`) — time TỪNG câu** | ✅ đo `time.perf_counter()` **mỗi câu** lúc chạy (không phải trung bình) |
| **`requirements.txt`** | ✅ [`requirements.txt`](requirements.txt) (+ `llama-cpp-python` build CUDA trong Dockerfile) |
| **README: Pipeline / Data / Resource Init + lệnh `docker run`** | ✅ ở trên + phần "Cách chạy" dưới |
| **GitHub public + DockerHub image** | ✅ [github.com/meiiie/bang_c](https://github.com/meiiie/bang_c) · `hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627` |
| **Mô hình ≤5B, một mô hình, không model/API ngoài** | ✅ Qwen3-4B-Instruct-2507 dense 4B, `local_llamacpp` offline |

## Đội thi — Neko Core

Trường **Đại học Hàng hải Việt Nam (VMU)**.

| Họ và tên | Lớp | Vai trò |
|---|---|---|
| Nguyễn Mạnh Hùng | CNT63ĐH | **Trưởng nhóm** (Team lead) |
| Bùi Việt Hoàng | CLC63ĐH | Thành viên |
| Phạm Thị Minh Hồng | CNT63ĐH | Thành viên |
| Phạm Thị Thu Thảo | KTN63ĐH | Thành viên |
| Nghiêm Thị Mỹ Linh | KPM63ĐH | Thành viên |

## Cách tái lập / chạy (Ban Tổ chức đọc phần này)

Bài nộp là **một Docker image offline, đã nướng sẵn mô hình**. Container đọc `/code/private_test.json`
và ghi `/code/submission.csv` + `/code/submission_time.csv`.

**Lệnh `docker run` chính thức** (mount thư mục chứa `private_test.json` vào `/code`):

```bash
docker pull hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627

mkdir -p code
cp private_test.json code/                 # đề ở /code/private_test.json
docker run --rm --gpus all -v "$PWD/code:/code" \
  hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627
# => ./code/submission.csv        (qid,answer)
#    ./code/submission_time.csv    (qid,answer,time)
```

> **Cờ chạy:** chỉ cần **`--gpus all`** + mount `/code`. **KHÔNG cần `--ipc=host` / `--shm-size`** —
> giải pháp dùng **llama.cpp in-process** (không phải vLLM), không dùng shared-memory liên tiến trình.

**Windows (PowerShell):**

```powershell
docker pull hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627
mkdir code -Force
copy private_test.json code\
docker run --rm --gpus all -v "${PWD}\code:/code" `
  hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627
```

**Yêu cầu môi trường:**

| | |
|---|---|
| GPU | **NVIDIA RTX 5060 Ti** (Blackwell, 16GB) — image build CUDA 12.8 + native `sm_120` + PTX floor `sm_75`. Cần driver hợp **CUDA ≥ 12.8** |
| Docker | Docker Engine + **NVIDIA Container Toolkit** (cho `--gpus all`) |
| Dung lượng | ~20GB cho image |
| Mạng | chỉ cần lúc `docker pull`; **lúc chạy hoàn toàn offline** |

### Hợp đồng đầu vào / đầu ra

| Hạng mục | Giá trị |
|---|---|
| File đầu vào | `/code/private_test.json` (JSON list `{qid, question, choices[]}`) |
| File đầu ra | `/code/submission.csv` — cột `qid,answer` |
| File đầu ra | `/code/submission_time.csv` — cột `qid,answer,time` (giây/câu, đo lúc chạy) |
| Giá trị `answer` | 1 chữ cái theo số phương án của TỪNG câu (A, B, C, D…) |

### Tự kiểm thử nhanh

```bash
mkdir -p code
cat > code/private_test.json <<'JSON'
[
  {"qid":"test_0001","question":"2 + 2 = ?","choices":["3","4","5","6"]},
  {"qid":"test_0002","question":"Thủ đô của Việt Nam?","choices":["Hà Nội","Huế","Đà Nẵng","TP.HCM"]}
]
JSON
docker run --rm --gpus all -v "$PWD/code:/code" \
  hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627
cat code/submission.csv code/submission_time.csv
```

## Mô hình & tuân thủ quy tắc Bảng C

- LLM: **Qwen3-4B-Instruct-2507** (dense 4B, GGUF Q5_K_M), chạy local qua llama.cpp (offline). Tuân thủ
  luật ≤5B: **≤5B tham số, mở mô hình, một mô hình duy nhất, không mô hình/API ngoài, không embedding/rerank**.
- **BTC xác nhận:** GPU chấm **RTX 5060 Ti (Blackwell, 16GB), RAM 32GB, base image CUDA ≥ 12.8**;
  ≤5B tính theo TỔNG tham số; chỉ 1 LLM ≤5B. → Bài nộp tuân thủ tuyệt đối (1 LLM Qwen3-4B dense, CUDA 12.8).
- **Không gắn cứng đáp án public-test.**

### Kết quả đã đo (minh bạch)

- **Public-463 leaderboard: 83.59** — Qwen3-4B self-consistency (cùng engine). Bản ≤5B chưa fine-tune,
  chưa RAG (sàn an toàn). Hướng tăng điểm: LoRA fine-tune + RAG có kiểm soát — xem `docs/method-writeup-vi.md`.
- **Về tên "self-consistency":** strategy mang tên module này nhưng cấu hình `self_consistency_samples=1`
  ⇒ chạy đúng bằng **chain-of-thought k=1**. Đã đo voting k=5 không cải thiện → chốt k=1 để tối ưu Time.

### Tài liệu thuyết minh phương pháp (chấm điểm Ý tưởng)

- [`docs/method-writeup-vi.md`](docs/method-writeup-vi.md) — Tiếng Việt (chi tiết)
- [`docs/method-writeup.md`](docs/method-writeup.md) — English
- Bản trình bày **PPTX** nộp riêng theo kênh BTC.

---

## Developer reference (English)

Config-first harness: model/provider/thresholds live in `configs/default.json`, not in source. The
submitted container is minimal and offline.

### Project structure

```text
predict.py             BTC Round-2 entry: /code/private_test.json -> /code/submission.csv + submission_time.csv
inference.sh           CMD ["bash","/app/inference.sh"] -> python3 predict.py   (code at /app, not /code)
Dockerfile.qwen-submission   Round-2 image (CUDA 12.8, Blackwell sm_120, Qwen3-4B Q5_K_M baked in)
src/hackaithon_c/      Harness: loader -> classifier -> prompting -> solver -> normalizer -> exporter
configs/default.json   Config-first runtime: providers, model paths, thresholds, runtime.model_policy
docker/                qwen-selfconsist.neko-core.json (baked ≤5B config overlay)
tests/                 Unit tests (python -m unittest discover -s tests)
docs/ , notes/         Method write-up, architecture, measured-result analysis
```

### Build the contest image (reproducibility)

```bash
# From this commit. Source-builds llama-cpp-python (GGML_NATIVE=OFF, CUDA 12.8, native sm_120 + PTX
# floor sm_75) and bakes Qwen3-4B-Instruct-2507 Q5_K_M GGUF. No public-test answers in any layer.
docker build -f Dockerfile.qwen-submission \
  -t hacamy12345/neko-core:qwen3-4b-r2-cuda128-20260627 .
```

### Run locally (development)

```bash
# No-model wiring/format test (deterministic heuristic, no GPU):
NEKO_DRY_RUN=1 python predict.py path/to/public-test.json
# -> submission.csv + submission_time.csv (validates I/O + per-sample timing)
```

`NEKO_INPUT` overrides the input path; `NEKO_OUTPUT_DIR` overrides where the CSVs are written.
