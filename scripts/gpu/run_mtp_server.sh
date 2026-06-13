#!/usr/bin/env bash
# Measure Gemma-4 MTP through llama-server, not llama-cli.
#
# Why server: recent llama.cpp master builds made llama-cli behave like an
# interactive REPL for this workload, while llama-server is also the production
# integration path for Neko Core's `local_server` provider.
set -euo pipefail

OWNER_SIGNOFF="${OWNER_SIGNOFF:-0}"
if [[ "$OWNER_SIGNOFF" != "1" ]]; then
  echo "Refusing to start GPU/model work. Set OWNER_SIGNOFF=1 after explicit owner approval." >&2
  exit 3
fi

WORKSPACE="${WORKSPACE:-/workspace}"
REPO_DIR="${REPO_DIR:-$WORKSPACE/bang_c}"
LLAMA_DIR="${LLAMA_DIR:-$WORKSPACE/llama.cpp}"
MODEL_DIR="${MODEL_DIR:-$WORKSPACE/m}"
OUT_DIR="${OUT_DIR:-$WORKSPACE/mtp_server_logs}"
PORT="${PORT:-8080}"
CTX_SIZE="${CTX_SIZE:-4096}"
N_PREDICT="${N_PREDICT:-2048}"
LLAMA_CPP_REF="${LLAMA_CPP_REF:-master}"
TEMPERATURE="${TEMPERATURE:-0.0}"
TOP_P="${TOP_P:-0.1}"
TOP_K="${TOP_K:-64}"
WARMUP_REQUESTS="${WARMUP_REQUESTS:-1}"
WARMUP_N_PREDICT="${WARMUP_N_PREDICT:-32}"
MEASURE_REQUESTS="${MEASURE_REQUESTS:-3}"
REQUIRE_CONTENT_MATCH="${REQUIRE_CONTENT_MATCH:-1}"
REQUIRE_DRAFT_ACCEPTANCE="${REQUIRE_DRAFT_ACCEPTANCE:-0}"
REQUIRE_SPEC_INIT="${REQUIRE_SPEC_INIT:-0}"
SERVER_PID=""
BENCH_INPUT_PATH="${BENCH_INPUT_PATH:-}"
BENCH_CONFIG_PATH="${BENCH_CONFIG_PATH:-}"
BENCH_PROMPT_SELECTION="${BENCH_PROMPT_SELECTION:-longest}"
BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE:-reasoning}"
BENCH_ENDPOINT="${BENCH_ENDPOINT:-chat}"
PROMPT_MESSAGES_FILE="${PROMPT_MESSAGES_FILE:-}"
PROMPT_SOURCE="default"

MAIN_REPO="${MAIN_REPO:-google/gemma-4-26B-A4B-it-qat-q4_0-gguf}"
MAIN_FILE="${MAIN_FILE:-gemma-4-26B_q4_0-it.gguf}"
DRAFT_REPO="${DRAFT_REPO:-unsloth/gemma-4-26B-A4B-it-GGUF}"
DRAFT_FILES=(
  "${DRAFT_FILE:-mtp-gemma-4-26B-A4B-it.gguf}"
  "MTP/${DRAFT_FILE:-mtp-gemma-4-26B-A4B-it.gguf}"
)

DEFAULT_PROMPT="You are a careful exam solver. Think step by step, then answer.
Question: A train travels 240 km in 3 hours, then 180 km in 2 hours. What is its average speed for the whole trip in km/h?
Choices: A) 80  B) 84  C) 90  D) 86
Reason briefly then give the final letter."

mkdir -p "$WORKSPACE" "$MODEL_DIR" "$OUT_DIR"
exec > >(tee -a "$OUT_DIR/run.log") 2>&1
cd "$WORKSPACE"

export PATH="/usr/local/cuda/bin:${PATH}"
export CUDACXX="${CUDACXX:-/usr/local/cuda/bin/nvcc}"
export DEBIAN_FRONTEND=noninteractive

log() {
  echo "=== [$(date +%H:%M:%S)] $* ==="
}

fail() {
  echo "FAILED: $*" >&2
  touch "$WORKSPACE/FAILED"
  exit 1
}

prepare_benchmark_prompt() {
  if [ -n "${PROMPT_FILE:-}" ]; then
    test -f "$PROMPT_FILE" || fail "PROMPT_FILE not found: $PROMPT_FILE"
    PROMPT="$(cat "$PROMPT_FILE")"
    PROMPT_SOURCE="file:$PROMPT_FILE"
  elif [ -n "${PROMPT+x}" ]; then
    PROMPT_SOURCE="env:PROMPT"
  elif [ -n "$BENCH_INPUT_PATH" ]; then
    test -f "$BENCH_INPUT_PATH" || fail "BENCH_INPUT_PATH not found: $BENCH_INPUT_PATH"
    local exporter="$REPO_DIR/scripts/export_mtp_benchmark_prompt.py"
    test -f "$exporter" || fail "missing prompt exporter: $exporter"
    local config_args=()
    if [ -n "$BENCH_CONFIG_PATH" ]; then
      test -f "$BENCH_CONFIG_PATH" || fail "BENCH_CONFIG_PATH not found: $BENCH_CONFIG_PATH"
      config_args=(--config "$BENCH_CONFIG_PATH")
    fi
    PYTHONPATH="$REPO_DIR/src:${PYTHONPATH:-}" python "$exporter" \
      --input "$BENCH_INPUT_PATH" \
      "${config_args[@]}" \
      --selection "$BENCH_PROMPT_SELECTION" \
      --prompt-mode "$BENCH_PROMPT_MODE" \
      --prompt-out "$OUT_DIR/benchmark-prompt.txt" \
      --messages-out "$OUT_DIR/benchmark-messages.json" \
      --metadata-out "$OUT_DIR/benchmark-prompt-metadata.json" || fail "export benchmark prompt"
    PROMPT="$(cat "$OUT_DIR/benchmark-prompt.txt")"
    PROMPT_MESSAGES_FILE="$OUT_DIR/benchmark-messages.json"
    PROMPT_SOURCE="input:$BENCH_INPUT_PATH"
  else
    PROMPT="$DEFAULT_PROMPT"
    printf "%s" "$PROMPT" >"$OUT_DIR/benchmark-prompt.txt"
  fi

  if [ ! -f "$OUT_DIR/benchmark-prompt.txt" ]; then
    printf "%s" "$PROMPT" >"$OUT_DIR/benchmark-prompt.txt"
  fi
  python - "$OUT_DIR/benchmark-prompt-source.json" "$PROMPT_SOURCE" "$BENCH_INPUT_PATH" \
    "$BENCH_PROMPT_SELECTION" "$BENCH_PROMPT_MODE" "$BENCH_ENDPOINT" "$PROMPT_MESSAGES_FILE" "$PROMPT" <<'PY'
import hashlib
import json
import sys

out, source, input_path, selection, mode, endpoint, messages_file, prompt = sys.argv[1:9]
payload = {
    "source": source,
    "input_path": input_path,
    "selection": selection,
    "prompt_mode": mode,
    "endpoint": endpoint,
    "messages_file": messages_file,
    "prompt_chars": len(prompt),
    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
}
with open(out, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
  log "benchmark prompt source: $PROMPT_SOURCE ($(wc -c <"$OUT_DIR/benchmark-prompt.txt") bytes)"
}

ensure_port_free() {
  local port="$1"
  python - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(1.0)
    raise SystemExit(1 if sock.connect_ex(("127.0.0.1", port)) == 0 else 0)
PY
}

cleanup() {
  local status=$?
  if [ -n "${SERVER_PID:-}" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if [ "$status" -ne 0 ] && [ ! -f "$WORKSPACE/SRV_DONE" ]; then
    touch "$WORKSPACE/FAILED"
  fi
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

log "start mtp server benchmark"
log "check port availability"
ensure_port_free "$PORT" || fail "port ${PORT} is already occupied"
prepare_benchmark_prompt
nvidia-smi | tee "$OUT_DIR/nvidia-smi-start.log"
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d '.')
echo "compute_cap=$CC" | tee "$OUT_DIR/gpu.txt"

log "install build tools"
if ! command -v cmake >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  apt-get update -qq >"$OUT_DIR/apt.log" 2>&1
  apt-get install -y -qq cmake build-essential git libgomp1 curl ca-certificates >>"$OUT_DIR/apt.log" 2>&1 || {
    tail -80 "$OUT_DIR/apt.log" >&2 || true
    fail "apt install"
  }
fi
cmake --version | tee "$OUT_DIR/cmake-version.log"

log "clone or update llama.cpp"
if [ ! -d "$LLAMA_DIR/.git" ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_DIR" >"$OUT_DIR/git-clone.log" 2>&1 || {
    tail -80 "$OUT_DIR/git-clone.log" >&2 || true
    fail "git clone llama.cpp"
  }
fi

cd "$LLAMA_DIR"
git fetch --depth 1 origin "$LLAMA_CPP_REF" >"$OUT_DIR/git-fetch.log" 2>&1 || {
  tail -80 "$OUT_DIR/git-fetch.log" >&2 || true
  fail "git fetch llama.cpp ref $LLAMA_CPP_REF"
}
git checkout --detach FETCH_HEAD >"$OUT_DIR/git-checkout.log" 2>&1 || {
  tail -80 "$OUT_DIR/git-checkout.log" >&2 || true
  fail "git checkout llama.cpp ref $LLAMA_CPP_REF"
}
git rev-parse HEAD | tee "$OUT_DIR/llama-commit.txt"

log "configure llama.cpp cuda build"
cmake -B build \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES="$CC" \
  -DLLAMA_CURL=OFF \
  -DCMAKE_BUILD_TYPE=Release >"$OUT_DIR/cmake-configure.log" 2>&1 || {
    tail -120 "$OUT_DIR/cmake-configure.log" >&2 || true
    fail "cmake configure"
  }

patch_ui_assets() {
  # llama.cpp master briefly generated zero-sized C++ arrays for UI assets.
  # Patching the generated file is harmless when the bug is absent.
  if [ -f build/tools/ui/ui.cpp ]; then
    sed -i 's/\[\] = {};/[] = {0};/g' build/tools/ui/ui.cpp
  fi
}

patch_ui_assets
log "build llama-server"
if ! cmake --build build --config Release -j --target llama-server >"$OUT_DIR/build.log" 2>&1; then
  patch_ui_assets
  cmake --build build --config Release -j --target llama-server >>"$OUT_DIR/build.log" 2>&1 || {
    tail -160 "$OUT_DIR/build.log" >&2 || true
    fail "build llama-server"
  }
fi

export LD_LIBRARY_PATH="$LLAMA_DIR/build/bin:$LLAMA_DIR/build/lib:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}"
SERVER="$LLAMA_DIR/build/bin/llama-server"
test -x "$SERVER" || fail "missing llama-server"

log "llama diagnostics"
"$SERVER" --version 2>&1 | tee "$OUT_DIR/llama-version.log"
"$SERVER" --list-devices 2>&1 | tee "$OUT_DIR/llama-devices.log" || true
"$SERVER" --help >"$OUT_DIR/llama-server-help.txt" 2>&1 || true
for flag in \
  "--spec-type" \
  "--model-draft" \
  "--spec-draft-n-max" \
  "--spec-draft-type-k" \
  "--spec-draft-type-v" \
  "--spec-draft-ngl" \
  "--spec-draft-device"; do
  grep -q -- "$flag" "$OUT_DIR/llama-server-help.txt" || fail "llama-server help missing $flag"
done
grep -q -- "draft-mtp" "$OUT_DIR/llama-server-help.txt" || fail "llama-server help missing draft-mtp spec type"
ldd "$SERVER" 2>&1 | tee "$OUT_DIR/ldd-llama-server.log"
CUDA_SO=$(find "$LLAMA_DIR/build" -maxdepth 3 -name 'libggml-cuda.so*' | head -1 || true)
test -n "$CUDA_SO" || fail "missing CUDA backend library"
ldd "$CUDA_SO" 2>&1 | tee "$OUT_DIR/ldd-cuda-backend.log"

log "download models"
if [ -z "${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}" ]; then
  log "warning: HF_TOKEN/HUGGING_FACE_HUB_TOKEN not set; gated Gemma downloads may fail"
fi
python -m pip -q install "huggingface-hub>=0.32,<1" >"$OUT_DIR/pip.log" 2>&1 || fail "pip install huggingface-hub"

MAIN=$(python - "$MAIN_REPO" "$MAIN_FILE" "$MODEL_DIR" <<'PY'
import sys
from huggingface_hub import hf_hub_download
print(hf_hub_download(repo_id=sys.argv[1], filename=sys.argv[2], local_dir=sys.argv[3]))
PY
) || fail "download main model"

DRAFT=$(python - "$DRAFT_REPO" "$MODEL_DIR" "${DRAFT_FILES[@]}" <<'PY'
import sys
from huggingface_hub import hf_hub_download

repo = sys.argv[1]
local_dir = sys.argv[2]
last_error = None
for filename in sys.argv[3:]:
    try:
        print(hf_hub_download(repo_id=repo, filename=filename, local_dir=local_dir))
        break
    except Exception as error:  # noqa: BLE001
        last_error = error
else:
    raise SystemExit(f"could not download draft model from {repo}: {last_error}")
PY
) || fail "download draft model"

echo "MAIN=$MAIN" | tee "$OUT_DIR/models.txt"
echo "DRAFT=$DRAFT" | tee -a "$OUT_DIR/models.txt"
ls -lh "$MODEL_DIR"/*.gguf "$MODEL_DIR"/MTP/*.gguf 2>/dev/null | tee "$OUT_DIR/model-files.txt" || true

python - "$OUT_DIR/launch-config.json" \
  "$WORKSPACE" "$REPO_DIR" "$LLAMA_DIR" "$MODEL_DIR" "$OUT_DIR" "$PORT" "$CTX_SIZE" \
  "$N_PREDICT" "$LLAMA_CPP_REF" "$TEMPERATURE" "$TOP_P" "$TOP_K" \
  "$WARMUP_REQUESTS" "$WARMUP_N_PREDICT" "$MEASURE_REQUESTS" \
  "$REQUIRE_CONTENT_MATCH" "$REQUIRE_DRAFT_ACCEPTANCE" "$REQUIRE_SPEC_INIT" \
  "$PROMPT_SOURCE" "$BENCH_INPUT_PATH" "$BENCH_PROMPT_SELECTION" "$BENCH_PROMPT_MODE" \
  "$BENCH_ENDPOINT" "$PROMPT_MESSAGES_FILE" \
  "$PROMPT" "$MAIN" "$DRAFT" <<'PY'
import json
import sys

keys = (
    "WORKSPACE",
    "REPO_DIR",
    "LLAMA_DIR",
    "MODEL_DIR",
    "OUT_DIR",
    "PORT",
    "CTX_SIZE",
    "N_PREDICT",
    "LLAMA_CPP_REF",
    "TEMPERATURE",
    "TOP_P",
    "TOP_K",
    "WARMUP_REQUESTS",
    "WARMUP_N_PREDICT",
    "MEASURE_REQUESTS",
    "REQUIRE_CONTENT_MATCH",
    "REQUIRE_DRAFT_ACCEPTANCE",
    "REQUIRE_SPEC_INIT",
    "PROMPT_SOURCE",
    "BENCH_INPUT_PATH",
    "BENCH_PROMPT_SELECTION",
    "BENCH_PROMPT_MODE",
    "BENCH_ENDPOINT",
    "PROMPT_MESSAGES_FILE",
    "PROMPT",
    "main_model",
    "draft_model",
)
values = sys.argv[2:]
if len(values) != len(keys):
    raise SystemExit(f"launch-config mismatch: got {len(values)} values for {len(keys)} keys")
payload = dict(zip(keys, values))
payload["endpoint"] = "/v1/chat/completions" if payload["BENCH_ENDPOINT"] == "chat" else "/completion"
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY

request_json() {
  local n_predict="${1:-$N_PREDICT}"
  python - "$BENCH_ENDPOINT" "$PROMPT" "$PROMPT_MESSAGES_FILE" "$n_predict" "$TEMPERATURE" "$TOP_P" "$TOP_K" <<'PY'
import json
import sys
from pathlib import Path

endpoint, prompt, messages_file = sys.argv[1:4]
n_predict = int(sys.argv[4])
temperature = float(sys.argv[5])
top_p = float(sys.argv[6])
top_k = int(sys.argv[7])
if endpoint == "chat":
    if messages_file:
        data = json.loads(Path(messages_file).read_text(encoding="utf-8"))
        messages = data["messages"]
    else:
        messages = [{"role": "user", "content": prompt}]
    print(json.dumps({
        "model": "local",
        "messages": messages,
        "max_tokens": n_predict,
        "temperature": temperature,
        "top_p": top_p,
        "seed": 42,
        "stream": False,
    }))
else:
    print(json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "seed": 42,
    }))
PY
}

completion_url() {
  if [ "$BENCH_ENDPOINT" = "chat" ]; then
    echo "http://127.0.0.1:${PORT}/v1/chat/completions"
  else
    echo "http://127.0.0.1:${PORT}/completion"
  fi
}

parse_response() {
  local label="$1"
  local response="$2"
  local server_log="$3"
  local request_index="$4"
  python - "$label" "$response" "$server_log" "$request_index" <<'PY'
import json
import hashlib
import re
import sys
from pathlib import Path

label, response_path, log_path, request_index = sys.argv[1:5]
payload = json.loads(Path(response_path).read_text(encoding="utf-8"))
timings = payload.get("timings") or {}
content = payload.get("content", "")
if "choices" in payload:
    try:
        content = payload["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        content = payload["choices"][0].get("text", content)
if not isinstance(content, str):
    content = json.dumps(content, ensure_ascii=False, sort_keys=True)
text = Path(log_path).read_text(encoding="utf-8", errors="replace")
speculative_initialized = bool(
    re.search(r"adding speculative implementation 'draft-mtp'|speculative decoding context initialized", text, re.I)
)
accept = None
matches = list(re.finditer(
    r"draft acceptance(?:\s+rate)?\s*=\s*([0-9.]+)\s*\(\s*([0-9]+)\s+accepted\s*/\s*([0-9]+)\s+generated",
    text,
    re.I,
))
if matches:
    match = matches[-1]
    accept = {
        "rate": float(match.group(1)),
        "accepted": int(match.group(2)),
        "generated": int(match.group(3)),
    }
else:
    drafted = timings.get("draft_n") or timings.get("n_drafted")
    accepted = timings.get("draft_n_accepted") or timings.get("n_accept")
    if drafted is not None and accepted is not None:
        drafted_int = int(drafted)
        accepted_int = int(accepted)
        accept = {
            "rate": (accepted_int / drafted_int) if drafted_int else None,
            "accepted": accepted_int,
            "generated": drafted_int,
        }
print(json.dumps({
    "label": label,
    "request_index": int(request_index),
    "predicted_n": timings.get("predicted_n"),
    "predicted_per_second": timings.get("predicted_per_second"),
    "prompt_per_second": timings.get("prompt_per_second"),
    "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    "content_chars": len(content),
    "draft_acceptance": accept,
    "draft_acceptance_present": accept is not None,
    "speculative_initialized": speculative_initialized,
}, ensure_ascii=False))
PY
}

measure() {
  local label="$1"
  shift
  local server_log="$OUT_DIR/server-${label}.log"

  log "measure $label"
  if ! ensure_port_free "$PORT"; then
    fail "port ${PORT} is already serving before ${label}"
  fi
  "$SERVER" \
    -m "$MAIN" \
    -ngl 999 \
    --device CUDA0 \
    -fa on \
    -ctk f16 \
    -ctv f16 \
    -c "$CTX_SIZE" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --no-warmup \
    "$@" >"$server_log" 2>&1 &
  SERVER_PID=$!
  local spid=$SERVER_PID

  local ready=0
  for _ in $(seq 1 120); do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      ready=1
      break
    fi
    if ! kill -0 "$spid" 2>/dev/null; then
      tail -80 "$server_log" >&2 || true
      fail "server died during startup: $label"
    fi
    sleep 2
  done
  [ "$ready" = 1 ] || {
    tail -120 "$server_log" >&2 || true
    fail "server not healthy: $label"
  }

  for i in $(seq 1 "$WARMUP_REQUESTS"); do
    request_json "$WARMUP_N_PREDICT" | curl -fsS \
      "$(completion_url)" \
      -H 'Content-Type: application/json' \
      --data-binary @- \
      --max-time 300 >"$OUT_DIR/warmup-${label}-${i}.json" || {
        tail -120 "$server_log" >&2 || true
        fail "warmup request failed: $label"
      }
  done

  for j in $(seq 1 "$MEASURE_REQUESTS"); do
    local response="$OUT_DIR/response-${label}-${j}.json"
    request_json "$N_PREDICT" | curl -fsS \
      "$(completion_url)" \
      -H 'Content-Type: application/json' \
      --data-binary @- \
      --max-time 900 >"$response" || {
        tail -120 "$server_log" >&2 || true
        fail "completion request failed: $label request=$j"
      }
    parse_response "$label" "$response" "$server_log" "$j" | tee -a "$OUT_DIR/results.jsonl"
  done
  kill "$spid" 2>/dev/null || true
  wait "$spid" 2>/dev/null || true
  SERVER_PID=""
  sleep 2
}

: >"$OUT_DIR/results.jsonl"
measure baseline
for n in 1 2 4 6; do
  measure "mtp_n${n}" \
    --model-draft "$DRAFT" \
    --spec-type draft-mtp \
    --spec-draft-n-max "$n" \
    --spec-draft-type-k f16 \
    --spec-draft-type-v f16 \
    --spec-draft-ngl 999 \
    --spec-draft-device CUDA0
done

log "summary"
python - "$OUT_DIR/results.jsonl" "$REQUIRE_CONTENT_MATCH" "$REQUIRE_DRAFT_ACCEPTANCE" "$REQUIRE_SPEC_INIT" <<'PY' | tee "$OUT_DIR/summary.txt"
import json
import sys
from collections import defaultdict
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
require_content_match = sys.argv[2] == "1"
require_draft_acceptance = sys.argv[3] == "1"
require_spec_init = sys.argv[4] == "1"

def median(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2

by_label = defaultdict(list)
for row in rows:
    by_label[row["label"]].append(row)

baseline_rows = by_label.get("baseline", [])
baseline_tps = median([row.get("predicted_per_second") for row in baseline_rows])
baseline_hashes = {row.get("content_sha256") for row in baseline_rows if row.get("content_sha256")}
problems = []
if len(baseline_hashes) != 1:
    problems.append(f"baseline content was not deterministic: hashes={sorted(baseline_hashes)}")
baseline_hash = next(iter(baseline_hashes), None)
warnings = []

for label in sorted(by_label, key=lambda item: (item != "baseline", item)):
    label_rows = by_label[label]
    tps_values = [row.get("predicted_per_second") for row in label_rows]
    tps_median = median(tps_values)
    speedup = (tps_median / baseline_tps) if tps_median and baseline_tps else None
    hashes = {row.get("content_sha256") for row in label_rows if row.get("content_sha256")}
    content_matches = None
    if label != "baseline" and baseline_hash:
        content_matches = len(hashes) == 1 and baseline_hash in hashes
        if require_content_match and not content_matches:
            problems.append(f"{label} content did not match baseline: hashes={sorted(hashes)} baseline={baseline_hash}")
    spec_init = any(bool(row.get("speculative_initialized")) for row in label_rows)
    if label != "baseline" and not spec_init:
        message = f"{label} did not log draft-mtp speculative initialization"
        if require_spec_init:
            problems.append(message)
        else:
            warnings.append(message)
    acceptance_rows = [row["draft_acceptance"] for row in label_rows if row.get("draft_acceptance") is not None]
    if label != "baseline" and require_draft_acceptance and not acceptance_rows:
        problems.append(f"{label} did not expose draft acceptance metrics")
    accepted = [item.get("accepted") for item in acceptance_rows if isinstance(item, dict)]
    generated = [item.get("generated") for item in acceptance_rows if isinstance(item, dict)]
    rates = [item.get("rate") for item in acceptance_rows if isinstance(item, dict)]
    print(json.dumps({
        "label": label,
        "requests": len(label_rows),
        "predicted_per_second_values": tps_values,
        "predicted_per_second_median": tps_median,
        "speedup_vs_baseline_median": speedup,
        "content_hashes": sorted(hashes),
        "content_matches_baseline": content_matches,
        "speculative_initialized": spec_init,
        "draft_acceptance_present": bool(acceptance_rows),
        "draft_acceptance_rate_median": median(rates),
        "draft_accepted_total": sum(value for value in accepted if value is not None),
        "draft_generated_total": sum(value for value in generated if value is not None),
    }, ensure_ascii=False))

if problems:
    print(json.dumps({"verdict": "fail", "problems": problems}, ensure_ascii=False))
    raise SystemExit(1)
print(json.dumps({"verdict": "pass", "warnings": warnings}, ensure_ascii=False))
PY

nvidia-smi | tee "$OUT_DIR/nvidia-smi-end.log"
touch "$WORKSPACE/SRV_DONE"
log "done"
