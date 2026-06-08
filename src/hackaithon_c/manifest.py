from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import HarnessConfig
from .evaluation import RunSummary


@dataclass(frozen=True)
class RunManifest:
    schema_version: str
    created_at_utc: str
    brand: str
    config_path: str
    config_sha256: str
    input_path: str
    input_sha256: str
    output_path: str
    trace_dir: str
    workflow: str | None
    strategy: str
    dry_run: bool
    verify: bool
    model: str
    limit: int | None
    total_problems: int
    total_predictions: int
    argv: tuple[str, ...]


def build_run_manifest(
    *,
    config: HarnessConfig,
    input_path: Path,
    output_path: Path,
    trace_dir: Path,
    workflow: str | None,
    strategy: str,
    dry_run: bool,
    verify: bool,
    model: str,
    limit: int | None,
    summary: RunSummary,
    argv: tuple[str, ...],
) -> RunManifest:
    return RunManifest(
        schema_version="neko_core.run_manifest.v1",
        created_at_utc=datetime.now(UTC).isoformat(),
        brand=config.brand_name,
        config_path=str(config.path),
        config_sha256=_sha256_file(config.path),
        input_path=str(input_path),
        input_sha256=_sha256_file(input_path),
        output_path=str(output_path),
        trace_dir=str(trace_dir),
        workflow=workflow,
        strategy=strategy,
        dry_run=dry_run,
        verify=verify,
        model=model,
        limit=limit,
        total_problems=summary.total_problems,
        total_predictions=summary.total_predictions,
        argv=argv,
    )


def write_run_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
