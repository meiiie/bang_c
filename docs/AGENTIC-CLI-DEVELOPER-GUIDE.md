# Neko Core — Hướng dẫn phát triển AI Agentic CLI

> Tài liệu kỹ thuật chuyên sâu, độc lập với cuộc thi. Mục tiêu: bất kỳ ai (kể cả sau khi
> HackAIthon kết thúc) đều có thể **dùng lại Neko Core làm khung phát triển một AI Agentic CLI**
> — cắm mô hình/API mới, thêm workflow/agent/tool, mở rộng pipeline — mà không phải đọc lại mã nguồn.

Mục lục:
1. [Triết lý & tổng quan](#1-triết-lý--tổng-quan)
2. [Kiến trúc pipeline (vòng lặp agentic)](#2-kiến-trúc-pipeline-vòng-lặp-agentic)
3. [Hệ thống cấu hình (config-first)](#3-hệ-thống-cấu-hình-config-first)
4. [Nhà cung cấp mô hình & thiết lập API](#4-nhà-cung-cấp-mô-hình--thiết-lập-api)
5. [Bảng biến môi trường (env vars)](#5-bảng-biến-môi-trường-env-vars)
6. [Workflow & chiến lược (strategies)](#6-workflow--chiến-lược-strategies)
7. [Các registry agentic (agents / tools / commands / capabilities)](#7-các-registry-agentic)
8. [Mở rộng](#8-mở-rộng)
9. [Quy trình phát triển & kiểm thử](#9-quy-trình-phát-triển--kiểm-thử)
10. [Nguyên tắc thiết kế](#10-nguyên-tắc-thiết-kế)

---

## 1. Triết lý & tổng quan

Neko Core là một **harness suy luận config-first**: mô hình, nhà cung cấp (provider), ngưỡng,
trọng số chấm điểm — **đều nằm trong cấu hình, không nằm trong mã nguồn**. Một lệnh CLI
(`python -m hackaithon_c.run …`) đọc một tập câu hỏi, chạy một *workflow* (chuỗi agent/strategy),
và ghi kết quả ra một file theo hợp đồng cố định.

Điểm mạnh để tái dùng làm Agentic CLI:
- **Một đường dữ liệu rõ ràng** input → classify → prompt → solve → normalize → validate → export.
- **Provider trừu tượng hoá**: cùng một harness chạy được mô hình local (GGUF/llama.cpp), local-server
  (llama-server HTTP), hoặc bất kỳ API OpenAI-compatible nào (NVIDIA NIM, FPT AI, OpenAI…).
- **Registry agentic**: vai trò (agents), công cụ (tools), lệnh (commands), năng lực (capabilities),
  workflow — tất cả khai báo tường minh, kiểm tra được qua CLI (`--agents`, `--tools`, `--commands`).
- **Hợp đồng + truy vết**: mọi lần chạy sinh trace/summary/manifest để tái lập và kiểm toán.

## 2. Kiến trúc pipeline (vòng lặp agentic)

```text
            ┌──────────── configs/default.json (config-first) ────────────┐
            │  provider · model · profile · thresholds · workflow · rubric │
            └──────────────────────────────────────────────────────────────┘
                                       │
  /data/*_test.(csv|json)              ▼
        │            loader.py ──► schema.py (Problem) ──► classifier.py
        │                                                     (kind, variant,
        │                                                      verify?, tournament?)
        │                                                          │
        │                                                          ▼
        │                                   prompting.py (build prompt theo variant)
        │                                                          │
        │                                                          ▼
        │                                solver.py (strategy: direct/verify/tournament/
        │                                   auto/self_consistency/tir/reading/rag/router)
        │                                                          │
        │                          model_client.build_chat_client(provider) ──► LLM
        │                                                          │
        │                                                          ▼
        │                              normalize.py (trích chữ cái) ─► (repair pass nếu cần)
        │                                                          │
        │                                                          ▼
        │                            calibration.py (confidence) · checkpoint.py (resume)
        │                                                          │
        ▼                                                          ▼
  exporter.py ──► /output/pred.csv (qid,answer)   +   traces/ run-summary.json run-manifest.json
```

Các module cốt lõi (`src/hackaithon_c/`):

| Module | Vai trò |
|---|---|
| `run.py` | Điểm vào CLI (argparse): chọn workflow/profile, chạy, ghi artifact. |
| `loader.py` + `schema.py` | Đọc CSV/JSON → đối tượng `Problem` (qid, question, choices…). |
| `classifier.py` | Phân loại câu hỏi (kind: calculation/reading/negative/many_choice/short…; variant; có verify/tournament không). |
| `prompting.py` | Dựng prompt theo variant (reasoning / calculation / evidence / reading…). |
| `solver.py` | Điều phối strategy → gọi model client → tổng hợp (voting). |
| `model_client.py` | `build_chat_client(config, provider)` → chọn client theo provider. |
| `local_client.py` | Provider `local_llamacpp` (llama-cpp-python, GGUF offline). |
| `nvidia_client.py` | Provider `nvidia` / `local_server` (HTTP OpenAI-compatible). |
| `normalize.py` | Trích chữ cái đáp án từ output mô hình; xử lý đa lựa chọn (A–J). |
| `calibration.py` | Tính confidence từ độ đồng thuận (agreement). |
| `checkpoint.py` | Ghi/đọc checkpoint để `--auto-resume`. |
| `exporter.py` | Ghi `pred.csv` đúng hợp đồng (write-before-validate). |
| `config.py` | Nạp + hợp nhất config/profile/env → `HarnessConfig`. |
| `agents.py` `tool_registry.py` `command_registry.py` `capabilities.py` | Các registry agentic (xem §7). |

## 3. Hệ thống cấu hình (config-first)

Tất cả hành vi runtime nằm trong `src/hackaithon_c/resources/default.json` (hoặc một file config
truyền qua `--config`). Cấu trúc:

```jsonc
{
  "contest": { "input_candidates": [...], "output_file": "pred.csv", "output_columns": ["qid","answer"] },
  "runtime": {
    "active_profile": "gemma26b-q4-local",   // profile mặc định
    "provider": "local_llamacpp",            // provider mặc định
    "default_model": "…", "local_model_path": "/models/…gguf",
    "local_n_ctx": 8192, "local_n_gpu_layers": -1,
    "default_strategy": "auto",
    "self_consistency_samples": 1, "reasoning_max_tokens": 2048,
    "reasoning_temperature": 0.8, "reasoning_top_p": 0.95, "reasoning_top_k": 64,
    "enable_safety_refusal": true, "repair_invalid_output": true,
    "max_retries": 6, "timeout_seconds": 90,
    "provider_registry": { … },              // mô tả các provider
    "profiles": { … }                        // các cấu hình runtime đặt tên
  },
  "workflows": { … },                        // các workflow đặt tên (xem §6)
  "profiling": { "thresholds": {…}, "markers": {…} },  // luật phân loại đa ngôn ngữ
  "rubric": { "contract": 40, "reproducibility": 20, … }
}
```

**Thứ tự ưu tiên (override)**: `biến môi trường` › `--profile` (profile trong config) › `runtime`
mặc định trong config. Mục tiêu: thích nghi với biến thể đề/private-test **mà không sửa mã nguồn**.

```powershell
neko --profiles                       # liệt kê các profile
neko --profile nvidia-gemma31b-api --doctor
$env:HACKC_PROFILE = "gemma26b-q4-local"     # chọn profile qua env
neko --config path\to\custom.json …          # dùng config khác
```

## 4. Nhà cung cấp mô hình & thiết lập API

`build_chat_client(config, provider)` (`model_client.py`) trả về một client theo `provider`.
Ba provider có sẵn (khai báo trong `provider_registry`):

| Provider | Loại | Khi nào dùng |
|---|---|---|
| `local_llamacpp` | GGUF qua llama-cpp-python (offline, in-process) | **Mặc định thi**: tự chứa, không mạng. |
| `local_server` | llama.cpp `llama-server` HTTP (OpenAI-compatible, localhost) | Continuous batching → `--workers` chạy song song; nền cho MTP. |
| `nvidia` | Bất kỳ API **OpenAI-compatible** | Phát triển/eval; cắm NVIDIA NIM, FPT AI, OpenAI… |

### Cắm một API OpenAI-compatible bất kỳ (NVIDIA / FPT / OpenAI / …)

Provider `nvidia` (`nvidia_client.py`) thực ra là một client OpenAI-compatible tổng quát: nó POST
`{base_url}/chat/completions`. Chỉ cần 3 thứ — **base URL**, **API key**, **tên model**:

```powershell
$env:HACKC_PROVIDER = "nvidia"
$env:HACKC_API_KEY  = "<api-key-ngoai-git>"      # hoặc NVIDIA_API_KEY (alias)
$env:NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"   # đổi sang endpoint của bạn
$env:HACKC_LLM_MODEL = "google/gemma-4-31b-it"
neko --workflow contest-strict --input data\public_test.json --run-dir run-api
```

Hoặc khai báo sẵn thành một **profile** trong `configs/default.json` (đã có ví dụ `fpt-gemma-api`):

```jsonc
"profiles": {
  "my-openai-api": {
    "provider": "nvidia",
    "base_url": "https://api.openai.com/v1",
    "default_model": "gpt-4o-mini",
    "api_model": "gpt-4o-mini"
  }
}
```
→ rồi `neko --profile my-openai-api …`. (API key vẫn truyền qua env, **không bao giờ commit**.)

> ⚠️ Lưu ý template chat: `local_server` (llama-server) áp **chat template của GGUF**, có thể khác
> cách `local_llamacpp` (llama-cpp-python) xử lý — với mô hình không có "system role" (vd Gemma)
> nên **gộp system vào user** để giữ chỉ dẫn (đã làm trong `NvidiaConfig.merge_system_into_user`).

## 5. Bảng biến môi trường (env vars)

Mọi thứ điều khiển runtime đều có thể đặt qua env (ưu tiên cao nhất). Nhóm chính:

| Biến | Ý nghĩa |
|---|---|
| `HACKC_PROFILE` | Chọn profile runtime trong config. |
| `HACKC_PROVIDER` | `local_llamacpp` / `local_server` / `nvidia`. |
| `HACKC_DATA_DIR` · `HACKC_OUTPUT_DIR` | Thư mục đọc đề / ghi `pred.csv`. |
| **API (provider nvidia)** | |
| `HACKC_API_KEY` (hoặc `NVIDIA_API_KEY`) | API key (đọc ngoài git). |
| `NVIDIA_BASE_URL` | Base URL OpenAI-compatible. |
| `HACKC_LLM_MODEL` | Tên model API. |
| `HACKC_TIMEOUT_SECONDS` · `HACKC_MAX_RETRIES` · `HACKC_RETRY_BASE_DELAY_SECONDS` · `HACKC_RETRY_MAX_DELAY_SECONDS` | Timeout/retry. |
| **Local GGUF (provider local_llamacpp)** | |
| `HACKC_LOCAL_MODEL_PATH` | Đường dẫn file `.gguf`. |
| `HACKC_LOCAL_MODEL_ID` | Định danh model. |
| `HACKC_LLAMACPP_N_CTX` | Context length. |
| `HACKC_LLAMACPP_N_GPU_LAYERS` | Số layer offload GPU (`-1` = tất cả). |
| `HACKC_LLAMACPP_N_BATCH` · `HACKC_LLAMACPP_FLASH_ATTN` · `HACKC_LLAMACPP_CHAT_FORMAT` | Tinh chỉnh llama.cpp. |
| **Local server / MTP (entrypoint)** | |
| `HACKC_LOCAL_SERVER_URL` | URL llama-server (`http://127.0.0.1:8080/v1`). |
| `NEKO_LOCAL_SERVER_MODE=1` | Entrypoint khởi động llama-server (MTP) rồi chạy harness qua `local_server`, fallback về `local_llamacpp`. |
| `NEKO_LLAMA_SERVER_BIN` · `NEKO_MAIN_MODEL_PATH` · `NEKO_MTP_DRAFT_MODEL_PATH` · `NEKO_MTP_DRAFT_N_MAX` | Binary + model chính + model draft MTP + n-max. |
| `NEKO_HOLD=1` | Giữ container sống (chạy sshd) để smoke trên pod. |

## 6. Workflow & chiến lược (strategies)

Một **workflow** (khai báo trong `workflows` của config) là một preset: chọn `strategy`, có `verify`,
`dry_run`, và `phase` (`runtime` = đường thi an toàn; `development` = chỉ để đo/thử).

| Workflow | Strategy | Phase | Ghi chú |
|---|---|---|---|
| `self-consistency` | `self_consistency` | runtime | **MẶC ĐỊNH THI**: CoT k=1 + safety-refusal. |
| `contest-auto` / `contest-strict` | `auto` | runtime | Classifier tự quyết verify/tournament. |
| `quick-dry-run` | `auto` (dry) | development | Smoke hợp đồng, không gọi model. |
| `verify-all` / `tournament` | `verify` / `tournament` | development | Ép verify / nhiều variant + vote. |
| `tiered-consistency` / `tir` / `reading` / `rag` / `router` | tương ứng | development | Các đòn bẩy đã *build, đo, và phần lớn bị loại* (xem method-writeup). |

**Strategy** (lõi trong `solver.py`):
- `direct` — một lần gọi, prompt theo variant phân loại.
- `verify` — direct + một lần verifier.
- `tournament` — nhiều variant, majority vote, verifier tuỳ chọn.
- `auto` — classifier quyết định khi nào verify/tournament.
- `self_consistency` — CoT, k mẫu (mặc định k=1, temp=0 ⇒ tất định), vote theo đồng thuận.
- `tir` — model viết + **chạy Python** (sandbox offline) cho câu định lượng.
- `reading` — bám đoạn văn, vét từng phương án theo văn bản.
- `rag` — BM25 trên corpus offline (chỉ khi `rag_corpus_path` được set).
- `router` — định tuyến theo loại câu (định lượng→TIR, đoạn văn→reading, …).

## 7. Các registry agentic

Neko Core mượn kỷ luật "mọi thứ khai báo tường minh + kiểm tra được" (kiểu Claude Code). Bốn registry:

- **Agents** (`--agents`, `--agent <name>`): vai trò trong harness — `runner`, `classifier`, `solver`,
  `verifier`, `reviewer`, `resolver`, session inspector, model inventory. Mỗi agent có: tools được phép,
  thứ được đọc/ghi, và ranh giới bàn giao (handoff).
- **Tools** (`--tools`, `--tool <name>`): hợp đồng công cụ — phase (runtime/development), trạng thái,
  lớp quyền, input/output, guardrail (vd `exporter`, `web-research`, `run_python`).
- **Commands** (`--commands`, `--command <name>`): mọi bề mặt CLI/script với phase, nhóm, ví dụ, guardrail.
- **Capabilities** (`--capabilities`): registry năng lực runtime vs development.

Kiểm tra nhanh:
```powershell
neko --agents ; neko --agent task-resolver
neko --tools  ; neko --tool exporter
neko --capabilities ; neko --list-workflows
neko --policy        # kiểm toán ranh giới runtime/development (gate trước khi nạp model)
```

## 8. Mở rộng

**Thêm một provider mới** (vd một SDK khác):
1. Tạo `xxx_client.py` với class có thuộc tính `model` + hàm `complete(system, user, *, max_tokens, …) -> str`
   (xem giao thức `ChatClient` trong `model_client.py`).
2. Đăng ký nhánh trong `build_chat_client()` theo `selected_provider == "xxx"`.
3. Thêm mô tả vào `runtime.provider_registry` (config) + một profile mẫu.

**Thêm một mô hình / endpoint**: chỉ cần một **profile** mới trong `configs/default.json` (provider +
base_url + model). Không sửa mã nguồn.

**Thêm một workflow**: thêm một mục vào `workflows` (strategy + verify + dry_run + phase). Nếu cần
một strategy mới, thêm nhánh trong `solver.py` và (nếu cần) một prompt builder trong `prompting.py`.

**Thêm tool/agent**: khai báo trong `tool_registry.py` / `agents.py` với hợp đồng đầy đủ (phase,
quyền, input/output, guardrail) để `--tools`/`--agents` và `--policy` nhìn thấy + kiểm soát.

## 9. Quy trình phát triển & kiểm thử

```powershell
.\scripts\bootstrap.ps1                       # .venv + cài editable + check nhanh
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests          # toàn bộ unit test
python -m compileall -q src
neko --doctor ; neko --policy                 # chẩn đoán môi trường + hợp đồng
neko --workflow quick-dry-run --input <test.json> --limit 5   # smoke không cần model
```

Vòng lặp đề xuất: chạy baseline → soi trace tin-cậy-thấp → thêm **một** thay đổi prompt/verifier
→ chạy lại cùng mẫu, so độ ổn định đáp án → chỉ giữ thay đổi cải thiện độ tái lập + tuân thủ.

Mỗi lần chạy có `--run-dir` sinh: `traces/predictions.trace.jsonl` (raw + normalized answer, strategy,
kind, confidence, fallback, các bước agent), `run-summary.json` (hợp đồng, đếm strategy/kind/fallback,
confidence, điểm rubric), `run-manifest.json` (hash config/input, model, args → tái lập).

## 10. Nguyên tắc thiết kế

- **Config-first, no god files** — hành vi trong config; module nhỏ, hợp đồng rõ.
- **Hợp đồng I/O điển hình** — đọc `/data`, ghi `/output/pred.csv` (`qid,answer`); ghi **trước** khi
  kiểm tra để một câu lỗi không zero cả lần chạy.
- **Runtime tách khỏi development** — container nộp bài offline, không web/subagent/DB; trace/eval/
  research ở ngoài artifact. `--policy` cưỡng chế ranh giới này.
- **Portable wheel** — build `llama-cpp-python` với `GGML_NATIVE=OFF` để chạy mọi CPU (Intel/AMD,
  có/không AVX-512). Tránh wheel prebuilt tối-ưu-CPU gây SIGILL trên máy lạ.
- **Mọi khẳng định phải đo được** — báo số thật (leaderboard hoặc mô hình thật), không phỏng đoán.
