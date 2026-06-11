"""Offline, sandboxed Python execution for tool-integrated reasoning (TIR).

The contest container runs with no network, so the residual risks of executing
model-written code are (a) runaway loops/CPU and (b) accidental filesystem writes —
NOT exfiltration. We contain both with a short-lived isolated subprocess:

- `sys.executable -I -S` : isolated mode (ignore PYTHON* env + user site) and skip
  site customization, so the child sees only the stdlib we ship.
- a hard wall-clock timeout (kills infinite loops),
- a working directory in a temp dir that is deleted afterwards,
- captured stdout/stderr, truncated to a bounded size.

This is a *robustness* sandbox, not an adversarial one — the code author is our own
LLM solving a math problem, not an attacker. Determinism: no Date/random seeding is
imposed here; numeric problems are deterministic, and the caller votes over samples.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# Pull the fenced code out of a model response. Accept ```python / ```py / ``` fences;
# fall back to the largest ```-delimited block; never execute un-fenced prose.
_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

_MAX_OUTPUT_CHARS = 4000


@dataclass(frozen=True)
class ExecResult:
    ok: bool
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def summary(self) -> str:
        """One short line for trace/debug: status + a stdout/stderr preview."""
        if self.timed_out:
            return "timed_out"
        tail = (self.stdout or self.stderr).strip().replace("\n", " ")
        return f"{'ok' if self.ok else 'error'}: {tail[:160]}"


def extract_code(text: str) -> str | None:
    """Return the Python code from the LAST fenced block, or None if there is none.

    The last block is preferred: when a model thinks aloud and revises, the final
    fence is its committed program.
    """
    if not text:
        return None
    blocks = _FENCE.findall(text)
    if not blocks:
        return None
    code = blocks[-1].strip()
    return code or None


def run_python(code: str, *, timeout_seconds: float = 5.0) -> ExecResult:
    """Execute `code` in an isolated, throwaway subprocess; capture stdout/stderr.

    Returns ExecResult(ok=False, timed_out=True) if it exceeds the wall clock, and
    ok=False with stderr on a non-zero exit. Never raises for ordinary failures —
    the caller decides how to degrade.
    """
    if not code or not code.strip():
        return ExecResult(ok=False, stdout="", stderr="empty code")
    with tempfile.TemporaryDirectory(prefix="neko_tir_") as work_dir:
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=work_dir,
                check=False,
            )
        except subprocess.TimeoutExpired as expired:
            partial = expired.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            return ExecResult(
                ok=False,
                stdout=partial[-_MAX_OUTPUT_CHARS:],
                stderr="execution timed out",
                timed_out=True,
            )
        except OSError as error:  # interpreter missing / spawn failure
            return ExecResult(ok=False, stdout="", stderr=f"spawn failed: {error}")
    return ExecResult(
        ok=completed.returncode == 0,
        stdout=(completed.stdout or "")[-_MAX_OUTPUT_CHARS:],
        stderr=(completed.stderr or "")[-_MAX_OUTPUT_CHARS:],
    )
