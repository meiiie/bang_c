# Neko Core

[![CI](https://github.com/meiiie/bang_c/actions/workflows/ci.yml/badge.svg)](https://github.com/meiiie/bang_c/actions/workflows/ci.yml)
[![Release](https://github.com/meiiie/bang_c/actions/workflows/release.yml/badge.svg)](https://github.com/meiiie/bang_c/actions/workflows/release.yml)

![Neko Core banner](docs/assets/neko-core-banner.png)

Trạng thái: bài dự thi **HackAIthon 2026 — Bảng C (Innovator) · Vòng 2**

**Neko Core** là một harness suy luận *config-first*, đóng gói thành **một Docker image offline, tự
chứa**. Theo đúng *Submission Guideline* của Ban Tổ chức (BTC) Vòng 2, container:

- **đọc** đề trắc nghiệm tại **`/code/private_test.json`** (BTC mount vào khi chấm),
- chạy mô hình **Qwen3-4B-Instruct-2507 (GGUF Q5_K_M, dense ≤5B)** ngay trong container,
- **ghi** kết quả ra **`submission.csv`** (`qid,answer`) và **`submission_time.csv`**
  (`qid,answer,time` — thời gian suy luận **từng câu**).

Không cần API key, không cần mạng, không mô hình/dịch vụ ngoài.

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
  predict.py       ── đo time.perf_counter() từng câu, ghi 2 file:
                         submission.csv        (qid,answer)
                         submission_time.csv   (qid,answer,time)
```

Entry-point là **`predict.py`** (gọi qua **`inference.sh`** — `CMD ["bash","inference.sh"]`). Nó tái
dùng nguyên đường giải đã được kiểm thử của harness (`solve_problem` + `repair_predictions_for_contract`),
chỉ thêm hợp đồng I/O của BTC và **đo thời gian từng câu** (vòng `for` theo từng item như BTC đề nghị).

## Data Processing

- **Đầu vào** là JSON dạng list, mỗi phần tử `{qid, question, choices[]}` (đúng định dạng public test
  BTC cấp). `loader.py` còn nhận CSV (`csv.DictReader`, chịu BOM) và tên cột không phân biệt hoa/thường
  (`qid/id`, `question/prompt`, `choices/options` hoặc các cột chữ cái `A,B,C,D…`).
- **Chuẩn hoá Unicode NFC**: tiếng Việt tổ hợp (NFD) tách token khác với dạng dựng sẵn (NFC) → mọi
  `question`/`choices` được `unicodedata.normalize("NFC", …)` để ổn định suy luận.
- **Không thu thập / huấn luyện dữ liệu** cho đường nộp này: image self-consistency thuần, không dùng
  tập huấn luyện ngoài, không gắn cứng đáp án public-test (mọi đòn bẩy phải tổng quát cho private 2000 câu).

## Resource Initialization

- **Mô hình**: tải sẵn **lúc build** từ Hugging Face (`unsloth/Qwen3-4B-Instruct-2507-GGUF`,
  `Qwen3-4B-Instruct-2507-Q5_K_M.gguf`) vào `/models/qwen3-4b.gguf` — **lúc chấm hoàn toàn offline**,
  không tải gì thêm.
- **Runtime suy luận**: `llama-cpp-python` được **build từ nguồn** với CUDA (`GGML_NATIVE=off` để chạy
  trên mọi CPU; native SASS `sm_70/75/80/86/89/90` + **PTX floor `compute_60`** để mọi GPU ≥ Pascal tự
  JIT lúc load). Biên dịch trên **base CUDA 12.2** đúng yêu cầu phần cứng BTC.
- **KHÔNG cần Vector Database / Indexing / RAG**: đường nộp này cố tình tối giản (robust > 1pp accuracy) —
  không corpus, không embedding, không rerank. Không có tài nguyên ngoài nào cần khởi tạo.

---

## Tuân thủ Submission Guideline (Vòng 2)

| Yêu cầu BTC | Đáp ứng |
|---|---|
| **Base image CUDA 12.2** | ✅ `nvidia/cuda:12.2.2-devel-ubuntu22.04` ([`Dockerfile.qwen-submission`](Dockerfile.qwen-submission)) |
| **Dockerfile build từ base sạch, model tải lúc build** | ✅ model tải từ HF trong layer build; image self-contained |
| **Entry-point `predict.py` đọc `/code/private_test.json`** | ✅ [`predict.py`](predict.py) (fallback robust sang `/data/*_test.{json,csv}`) |
| **`inference.sh` chạy pipeline đầu-cuối** | ✅ [`inference.sh`](inference.sh) — `CMD ["bash","inference.sh"]` |
| **Ghi `submission.csv` (`qid,answer`)** | ✅ ghi-trước-validate, đủ mọi `qid`, mỗi đáp án 1 chữ cái hợp lệ |
| **Ghi `submission_time.csv` (`qid,answer,time`)** | ✅ đo `time.perf_counter()` **từng câu** lúc chạy |
| **`requirements.txt`** | ✅ [`requirements.txt`](requirements.txt) (+ `llama-cpp-python` build CUDA trong Dockerfile) |
| **README: Pipeline / Data / Resource Init** | ✅ ba mục ở trên |
| **GitHub public + DockerHub image** | ✅ [github.com/meiiie/bang_c](https://github.com/meiiie/bang_c) · `hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626` |
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

## Cách tái lập kết quả (Ban Tổ chức đọc phần này)

Bài nộp là **một Docker image offline, đã nướng sẵn mô hình bên trong**. Hợp đồng đúng theo Submission
Guideline: container đọc `/code/private_test.json` và ghi `submission.csv` + `submission_time.csv`.

**Yêu cầu môi trường:**

| | |
|---|---|
| GPU | **NVIDIA** ≥ 6GB VRAM (image dùng ~5GB — server BTC 16GB thừa). Driver hợp **CUDA 12.2**. Multi-arch SASS `sm_70…90` + PTX floor `compute_60` → mọi GPU ≥ Pascal chạy được |
| Docker | Docker Engine + **NVIDIA Container Toolkit** (cho `--gpus all`) |
| Dung lượng | ~20GB trống cho image |
| Mạng | chỉ cần lúc `docker pull`; **lúc chạy hoàn toàn offline** |

**Chạy đúng như BTC chấm** (mount đề vào `/code/private_test.json`):

```bash
docker pull hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626

# Đặt private_test.json vào ./code rồi mount cả thư mục vào /code
mkdir -p code
cp private_test.json code/
docker run --rm --gpus all -v "$PWD/code:/code" \
  hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626
# => ./code/submission.csv         (qid,answer)
#    ./code/submission_time.csv     (qid,answer,time)
```

**Windows (PowerShell):**

```powershell
docker pull hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626
mkdir code -Force
copy private_test.json code\
docker run --rm --gpus all -v "${PWD}\code:/code" `
  hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626
```

Container tự dò đề (`/code/private_test.json` → fallback `/data/*_test.{json,csv}`), chạy workflow
`self-consistency` (k=1 CoT), và ghi 2 file kết quả vào `/code` (đồng thời `/output` để dự phòng).
`submission.csv` được **ghi đủ mọi `qid`** và mỗi đáp án là 1 chữ cái hợp lệ — một câu lỗi không bao
giờ làm hỏng (về 0) cả lần chạy. Mọi thứ **offline**.

### Hợp đồng đầu vào / đầu ra

| Hạng mục | Giá trị |
|---|---|
| File đầu vào | `/code/private_test.json` (JSON list `{qid, question, choices[]}`) |
| File đầu ra | `submission.csv` — cột `qid,answer` |
| File đầu ra | `submission_time.csv` — cột `qid,answer,time` (giây/câu, đo lúc chạy) |
| Giá trị `answer` | 1 chữ cái theo số phương án của TỪNG câu (A, B, C, D…) |

### Tự kiểm thử nhanh

```bash
# Tạo code/private_test.json mẫu rồi chạy y hệt lệnh trên:
cat > code/private_test.json <<'JSON'
[
  {"qid":"test_0001","question":"2 + 2 = ?","choices":["3","4","5","6"]},
  {"qid":"test_0002","question":"Thủ đô của Việt Nam?","choices":["Hà Nội","Huế","Đà Nẵng","TP.HCM"]}
]
JSON
docker run --rm --gpus all -v "$PWD/code:/code" \
  hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626
cat code/submission.csv code/submission_time.csv
# Kỳ vọng: submission.csv 2 dòng "qid,answer"; submission_time.csv 2 dòng "qid,answer,time".
```

### Chạy private test 2000 câu (Vòng 2)

Lệnh **giống hệt** — chỉ cần `private_test.json` thật trong `./code`. Pipeline sequential, đo thời gian
từng câu. Một mô hình 4B, VRAM ~5GB — không OOM trên GPU thi đấu.

## Mô hình & tuân thủ quy tắc Bảng C

- LLM: **Qwen3-4B-Instruct-2507** (dense 4B, GGUF Q5_K_M), chạy local qua llama.cpp (offline). Tuân thủ
  luật ≤5B: **≤5B tham số, mở mô hình, một mô hình duy nhất, không mô hình/API ngoài, không embedding/rerank**.
  Allowlist config-driven (`runtime.model_policy`): `{"aliases":["*"],"max_params_b":5.0}`.
- **BTC xác nhận (2026-06-18):** server chấm 16GB VRAM; ≤5B tính theo TỔNG tham số; chỉ 1 LLM ≤5B,
  không embedding/rerank. → Bài nộp tuân thủ tuyệt đối (1 LLM Qwen3-4B, ~5GB/16GB, không RAG/rerank).
- **Không gắn cứng đáp án public-test.**

### Kết quả đã đo (minh bạch)

- **Public-463 leaderboard: 83.59** — Qwen3-4B self-consistency (cùng engine, đo trên leaderboard chính
  thức). Bản ≤5B chưa fine-tune, chưa RAG (sàn an toàn). Hướng tăng điểm: LoRA fine-tune + RAG có kiểm
  soát — xem [`docs/method-writeup-vi.md`](docs/method-writeup-vi.md).
- **Về tên "self-consistency":** strategy mang tên module này nhưng cấu hình `self_consistency_samples=1`
  ⇒ chạy đúng bằng **chain-of-thought k=1** (1 mẫu/câu). Đã đo voting k=5 không cải thiện → chốt k=1 để
  tối ưu điểm Time.

### Tài liệu thuyết minh phương pháp (chấm điểm Ý tưởng)

- [`docs/method-writeup-vi.md`](docs/method-writeup-vi.md) — Tiếng Việt (chi tiết)
- [`docs/method-writeup.md`](docs/method-writeup.md) — English
- Bản trình bày **PPTX** nộp riêng theo kênh BTC.

---

## Developer reference (English)

Neko Core is a **config-first** harness: model/provider selection, thresholds, and rubric weights live
in `configs/default.json`, not in source. The submitted container is intentionally minimal and offline.

### Project structure

```text
predict.py             BTC Round-2 entry: /code/private_test.json -> submission.csv + submission_time.csv
inference.sh           CMD ["bash","inference.sh"] -> python3 predict.py
Dockerfile.qwen-submission   The Round-2 contest image (CUDA 12.2, Qwen3-4B Q5_K_M baked in)
src/hackaithon_c/      Harness: loader -> classifier -> prompting -> solver -> normalizer
                       -> contract validation -> exporter (+ config, calibration, checkpoint)
configs/default.json   Config-first runtime: providers, model paths, thresholds, runtime.model_policy
docker/                neko-entrypoint.sh + qwen-selfconsist.neko-core.json (baked ≤5B config overlay)
tests/                 Unit tests (python -m unittest discover -s tests)
docs/                  Method write-up, architecture, evaluation rubric
notes/                 Measured-result analysis (leaders + rejected levers, with numbers)
```

### Build the contest image (reproducibility)

```bash
# From this commit. Source-builds llama-cpp-python (GGML_NATIVE=OFF, CUDA 12.2 multi-arch)
# and bakes Qwen3-4B-Instruct-2507 Q5_K_M GGUF. No public-test answers baked into any layer.
docker build -f Dockerfile.qwen-submission \
  -t hacamy12345/neko-core:qwen3-4b-r2-cuda122-20260626 .
```

### Run locally (development)

```bash
# No-model wiring/format test (deterministic heuristic, no GPU):
NEKO_DRY_RUN=1 python predict.py path/to/public-test.json
# -> submission.csv + submission_time.csv (validates I/O + per-sample timing)
```

`NEKO_INPUT` overrides the input path; `NEKO_OUTPUT_DIR` overrides where the CSVs are written.

### Architecture & docs

- [`docs/AGENTIC-CLI-DEVELOPER-GUIDE.md`](docs/AGENTIC-CLI-DEVELOPER-GUIDE.md) — deep guide for Neko Core
- [`docs/harness-architecture.md`](docs/harness-architecture.md) — layered pipeline + contracts
- [`docs/evaluation-rubric.md`](docs/evaluation-rubric.md) — scoring model
- [`notes/2026-06-16-le5b-rules-and-model-policy.md`](notes/2026-06-16-le5b-rules-and-model-policy.md) —
  the ≤5B rules pivot + config-driven model policy + measured Qwen3-4B results
