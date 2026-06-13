#!/usr/bin/env bash
set -euo pipefail

if [[ "${NEKO_HOLD:-}" == "1" ]]; then
  echo "Neko Core hold mode enabled; container will stay alive for RunPod smoke tests."
  if command -v sshd >/dev/null 2>&1; then
    mkdir -p /run/sshd
    /usr/sbin/sshd || true
  elif command -v service >/dev/null 2>&1; then
    service ssh start || true
  fi
  exec sleep infinity
fi

NEKO_LOCAL_SERVER_PID=""

cleanup_local_server() {
  if [[ -n "${NEKO_LOCAL_SERVER_PID:-}" ]] && kill -0 "$NEKO_LOCAL_SERVER_PID" >/dev/null 2>&1; then
    kill "$NEKO_LOCAL_SERVER_PID" >/dev/null 2>&1 || true
    wait "$NEKO_LOCAL_SERVER_PID" 2>/dev/null || true
  fi
  NEKO_LOCAL_SERVER_PID=""
}
trap cleanup_local_server EXIT INT TERM

run_local_server_mode() {
  local python_bin="${NEKO_PYTHON_BIN:-python}"
  local server_bin="${NEKO_LLAMA_SERVER_BIN:-llama-server}"
  local main_model="${NEKO_MAIN_MODEL_PATH:-${HACKC_LOCAL_MODEL_PATH:-/models/gemma-4-26B_q4_0-it.gguf}}"
  local draft_model="${NEKO_MTP_DRAFT_MODEL_PATH:-${HACKC_MTP_DRAFT_MODEL_PATH:-/models/mtp-gemma-4-26B-A4B-it.gguf}}"
  local host="${NEKO_LOCAL_SERVER_HOST:-127.0.0.1}"
  local port="${NEKO_LOCAL_SERVER_PORT:-8080}"
  local ctx="${HACKC_LLAMACPP_N_CTX:-8192}"
  local ngl="${HACKC_LLAMACPP_N_GPU_LAYERS:--1}"
  local draft_n_max="${NEKO_MTP_DRAFT_N_MAX:-2}"
  local draft_ngl="${NEKO_MTP_DRAFT_NGL:-999}"
  local draft_device="${NEKO_MTP_DRAFT_DEVICE:-CUDA0}"
  local health_timeout="${NEKO_LOCAL_SERVER_HEALTH_TIMEOUT_SECONDS:-120}"
  local workers="${NEKO_LOCAL_SERVER_WORKERS:-1}"
  local base_url="http://${host}:${port}/v1"
  local health_url="http://${host}:${port}/health"

  if ! command -v "$server_bin" >/dev/null 2>&1; then
    echo "NEKO_LOCAL_SERVER_MODE=1 requires llama-server; not found: ${server_bin}" >&2
    return 1
  fi
  if [[ ! -f "$main_model" ]]; then
    echo "Main model file not found: ${main_model}" >&2
    return 1
  fi
  if [[ ! -f "$draft_model" ]]; then
    echo "MTP draft model file not found: ${draft_model}" >&2
    return 1
  fi
  if ! [[ "$health_timeout" =~ ^[0-9]+$ ]] || [[ "$health_timeout" -lt 1 ]]; then
    echo "NEKO_LOCAL_SERVER_HEALTH_TIMEOUT_SECONDS must be a positive integer" >&2
    return 1
  fi

  # Flags mirror scripts/gpu/run_mtp_server.sh (the config the 1.37x was measured on):
  # flash-attention + f16 KV on the main model, draft heads on the same CUDA device.
  "$server_bin" \
    -m "$main_model" \
    --host "$host" \
    --port "$port" \
    -c "$ctx" \
    -ngl "$ngl" \
    -fa on \
    -ctk f16 \
    -ctv f16 \
    --model-draft "$draft_model" \
    --spec-type draft-mtp \
    --spec-draft-n-max "$draft_n_max" \
    --spec-draft-ngl "$draft_ngl" \
    --spec-draft-device "$draft_device" \
    --spec-draft-type-k f16 \
    --spec-draft-type-v f16 &
  NEKO_LOCAL_SERVER_PID="$!"

  is_local_server_healthy() {
    "$python_bin" - "$health_url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
        raise SystemExit(0 if 200 <= response.status < 300 else 1)
except Exception:
    raise SystemExit(1)
PY
  }

  for _ in $(seq 1 "$health_timeout"); do
    if ! kill -0 "$NEKO_LOCAL_SERVER_PID" >/dev/null 2>&1; then
      wait "$NEKO_LOCAL_SERVER_PID" 2>/dev/null || true
      echo "llama-server exited before becoming healthy" >&2
      return 1
    fi
    if is_local_server_healthy; then
      break
    fi
    sleep 1
  done

  if ! is_local_server_healthy; then
    echo "llama-server did not become healthy within ${health_timeout}s" >&2
    return 1
  fi

  export HACKC_PROVIDER=local_server
  export HACKC_LOCAL_SERVER_URL="$base_url"

  if [[ "$#" -gt 0 ]]; then
    "$python_bin" -m hackaithon_c.run "$@"
  else
    "$python_bin" -m hackaithon_c.run \
      --workflow self-consistency \
      --provider local_server \
      --workers "$workers" \
      --data-dir /data \
      --output-dir /output \
      --run-dir /output/neko-run \
      --auto-resume \
      --checkpoint-every 1
  fi
}

if [[ "${NEKO_LOCAL_SERVER_MODE:-}" == "1" ]]; then
  # MTP fast path. If llama-server cannot start / stay healthy on the judge GPU,
  # fall back to the proven in-process local_llamacpp path so pred.csv is still
  # produced — a speed lever must never be able to zero the Accuracy score.
  if run_local_server_mode "$@"; then
    exit 0
  fi
  echo "NEKO_LOCAL_SERVER_MODE (MTP) failed; falling back to in-process local_llamacpp" >&2
  cleanup_local_server
  export HACKC_PROVIDER=local_llamacpp
  unset HACKC_LOCAL_SERVER_URL
  # fall through to the default in-process path below (re-uses /output checkpoints)
fi

if [[ "$#" -gt 0 ]]; then
  exec "${NEKO_PYTHON_BIN:-python}" -m hackaithon_c.run "$@"
fi

exec "${NEKO_PYTHON_BIN:-python}" -m hackaithon_c.run \
  --workflow self-consistency \
  --data-dir /data \
  --output-dir /output \
  --run-dir /output/neko-run \
  --auto-resume \
  --checkpoint-every 1
