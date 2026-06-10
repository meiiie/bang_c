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

if [[ "$#" -gt 0 ]]; then
  exec python -m hackaithon_c.run "$@"
fi

exec python -m hackaithon_c.run \
  --workflow self-consistency \
  --data-dir /data \
  --output-dir /output \
  --run-dir /output/neko-run \
  --auto-resume \
  --checkpoint-every 1
