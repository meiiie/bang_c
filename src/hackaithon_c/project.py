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
