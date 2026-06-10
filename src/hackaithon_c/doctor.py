from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .branding import version_line
from .config import HarnessConfig
from .loader import find_input_file
from .model_client import effective_provider


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
    provider: str | None = None,
) -> tuple[DoctorCheck, ...]:
    selected_provider = effective_provider(config, provider)
    checks: list[DoctorCheck] = [
        DoctorCheck("ok", "version", version_line(config)),
        DoctorCheck("ok", "config", str(config.path)),
        DoctorCheck("ok", "schema", config.schema_version),
        DoctorCheck("ok", "output", f"{config.output_file} {list(config.output_columns)}"),
        DoctorCheck("ok", "strategy", config.default_strategy),
        DoctorCheck("ok", "profile", config.active_profile or "none"),
        DoctorCheck("ok", "provider", selected_provider),
        DoctorCheck("ok", "model", _effective_model(config, selected_provider)),
    ]

    if selected_provider == "nvidia":
        key_status = "set" if os.environ.get("NVIDIA_API_KEY", "").strip() else "missing"
        checks.append(
            DoctorCheck(
                "ok" if key_status == "set" else "warn",
                "nvidia_key",
                key_status,
            )
        )
    else:
        model_path = Path(os.environ.get("HACKC_LOCAL_MODEL_PATH", config.local_model_path))
        checks.append(
            DoctorCheck(
                "ok" if model_path.exists() else "warn",
                "local_model",
                f"{model_path} ({'found' if model_path.exists() else 'missing'})",
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


def _effective_model(config: HarnessConfig, provider: str | None = None) -> str:
    selected_provider = provider or effective_provider(config)
    if selected_provider == "nvidia":
        return os.environ.get("HACKC_LLM_MODEL", config.api_model).strip() or config.api_model
    return os.environ.get("HACKC_LOCAL_MODEL_ID", config.default_model).strip() or config.default_model


def _safe_find_input(data_dir: Path, config: HarnessConfig) -> Path | None:
    try:
        return find_input_file(data_dir, config)
    except FileNotFoundError:
        return None
