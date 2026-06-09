#!/usr/bin/env bash
set -euo pipefail

DEFAULT_SOURCE="git+https://github.com/meiiie/bang_c.git"
SOURCE="${NEKO_INSTALL_SOURCE:-${1:-${DEFAULT_SOURCE}}}"

if [[ "${NEKO_NON_INTERACTIVE:-}" == "1" ]]; then
  export PIP_NO_INPUT=1
  export PIP_DISABLE_PIP_VERSION_CHECK=1
  echo "Neko Core installer: non-interactive mode enabled."
fi

resolve_python() {
  for candidate in python3.11 python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    if "$candidate" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(resolve_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python 3.11+ is required. Install Python 3.11+ and rerun this installer." >&2
  exit 1
fi

echo "Using Python: $(${PYTHON_BIN} -c 'import sys; print(sys.executable)')"
echo "Installing/upgrading pipx..."
"${PYTHON_BIN}" -m pip install --user --upgrade pipx

echo "Ensuring pipx app path is registered..."
"${PYTHON_BIN}" -m pipx ensurepath

PIPX_BIN_DIR="$("${PYTHON_BIN}" -m pipx environment --value PIPX_BIN_DIR 2>/dev/null || true)"
if [[ -z "${PIPX_BIN_DIR}" ]]; then
  PIPX_BIN_DIR="${HOME}/.local/bin"
fi
export PATH="${PIPX_BIN_DIR}:${PATH}"

echo "Installing Neko Core from ${SOURCE} ..."
"${PYTHON_BIN}" -m pipx install --force "${SOURCE}"

if command -v neko >/dev/null 2>&1; then
  neko --version
  echo "Neko Core installed."
  echo "Try: neko --doctor"
  echo "Run: neko --workflow contest-strict --data-dir data --output-dir output"
  echo "Alias: neko-core --doctor"
else
  echo "Neko Core installed, but the command is not visible in this shell yet." >&2
  echo "Open a new terminal or add ${PIPX_BIN_DIR} to PATH." >&2
fi
