from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import (
    DEFAULT_CONFIG_NAME,
    LOCAL_CONFIG_DIR,
    LOCAL_CONFIG_NAME,
    load_config,
)


@dataclass(frozen=True)
class ProjectInitResult:
    config_path: Path
    created: bool
    message: str


def init_project(root: Path, *, force: bool = False) -> ProjectInitResult:
    source_path = _source_config_path(root)
    target_dir = root / LOCAL_CONFIG_DIR
    target_path = target_dir / LOCAL_CONFIG_NAME

    if target_path.exists() and not force:
        return ProjectInitResult(
            config_path=target_path,
            created=False,
            message=f"Existing project config kept: {target_path}",
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() == target_path.resolve():
        _validate_json_file(target_path)
    else:
        shutil.copyfile(source_path, target_path)
        _validate_json_file(target_path)

    return ProjectInitResult(
        config_path=target_path,
        created=True,
        message=f"Project config ready: {target_path}",
    )


USER_CONFIG_TEMPLATE = {
    "_comment": (
        "Neko Core user config (like ~/.claude.json). Put your API key + chosen provider "
        "here to reuse Neko Core as an Agentic CLI WITHOUT a local model. Never commit "
        "this file. Env vars HACKC_API_KEY / NVIDIA_API_KEY override these values."
    ),
    "runtime": {
        "active_profile": "nvidia-gemma31b-api",
        "api_key": "",
        "_hint": (
            "Paste your key in api_key (or set HACKC_API_KEY). Switch provider via "
            "active_profile (e.g. fpt-gemma-api); list options with `neko --profiles`."
        ),
    },
}


def init_user_config(*, force: bool = False) -> ProjectInitResult:
    """Scaffold the user-level config at ``~/.neko-core/config.json`` — the claude.json-
    style home file that holds your API key + chosen provider. Only the keys you set
    override the baked default (it is merged on top)."""
    target_dir = Path.home() / LOCAL_CONFIG_DIR
    target_path = target_dir / LOCAL_CONFIG_NAME

    if target_path.exists() and not force:
        return ProjectInitResult(
            config_path=target_path,
            created=False,
            message=(
                f"Existing user config kept: {target_path} "
                "(use --force to overwrite)"
            ),
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(USER_CONFIG_TEMPLATE, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ProjectInitResult(
        config_path=target_path,
        created=True,
        message=(
            f"User config ready: {target_path}\n"
            "Edit \"api_key\" (and \"active_profile\" if needed), then run `neko --doctor`."
        ),
    )


def _validate_json_file(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8"))


def _source_config_path(root: Path) -> Path:
    candidates = (
        root / "configs" / DEFAULT_CONFIG_NAME,
        Path(__file__).resolve().parents[2] / "configs" / DEFAULT_CONFIG_NAME,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return load_config().path
