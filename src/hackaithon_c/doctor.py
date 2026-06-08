from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .branding import version_line
from .config import HarnessConfig
from .loader import find_input_file


@dataclass(frozen=True)
class DoctorCheck:
    status: str
    name: str
    detail: str


def collect_doctor_checks(
    config: HarnessConfig,
    *,
    data_dir: Path,
    input_path: Path | None = None,
) -> tuple[DoctorCheck, ...]:
    checks: list[DoctorCheck] = [
        DoctorCheck("ok", "version", version_line(config)),
        DoctorCheck("ok", "config", str(config.path)),
        DoctorCheck("ok", "schema", config.schema_version),
        DoctorCheck("ok", "output", f"{config.output_file} {list(config.output_columns)}"),
        DoctorCheck("ok", "strategy", config.default_strategy),
        DoctorCheck("ok", "model", _effective_model(config)),
    ]

    key_status = "set" if os.environ.get("NVIDIA_API_KEY", "").strip() else "missing"
    checks.append(
        DoctorCheck(
            "ok" if key_status == "set" else "warn",
            "nvidia_key",
            key_status,
        )
    )

    resolved_input = input_path or _safe_find_input(data_dir, config)
    if resolved_input is None:
        checks.append(
            DoctorCheck(
                "warn",
                "input",
                f"No contest input found in {data_dir}. Pass --input for local runs.",
            )
        )
    else:
        checks.append(DoctorCheck("ok", "input", str(resolved_input)))

    return tuple(checks)


def render_doctor_report(checks: tuple[DoctorCheck, ...]) -> str:
    lines = ["Neko Core doctor"]
    for check in checks:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.detail}")
    return "\n".join(lines)


def _effective_model(config: HarnessConfig) -> str:
    return os.environ.get("HACKC_LLM_MODEL", config.default_model).strip() or config.default_model


def _safe_find_input(data_dir: Path, config: HarnessConfig) -> Path | None:
    try:
        return find_input_file(data_dir, config)
    except FileNotFoundError:
        return None
