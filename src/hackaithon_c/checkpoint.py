from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import HarnessConfig
from .manifest import file_sha256
from .schema import Prediction, TraceStep

CHECKPOINT_NAME = "predictions.checkpoint.jsonl"
CHECKPOINT_META_NAME = "checkpoint.meta.json"


def checkpoint_path(trace_dir: Path) -> Path:
    return trace_dir / CHECKPOINT_NAME


def checkpoint_meta_path(trace_dir: Path) -> Path:
    return trace_dir / CHECKPOINT_META_NAME


def clear_checkpoint(trace_dir: Path) -> None:
    for path in (checkpoint_path(trace_dir), checkpoint_meta_path(trace_dir)):
        if path.exists():
            path.unlink()


def write_checkpoint_meta(
    trace_dir: Path,
    *,
    config: HarnessConfig,
    input_path: Path,
    workflow: str | None,
    strategy: str,
    dry_run: bool,
    verify: bool,
    model: str,
    total_problems: int,
) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "schema_version": "neko_core.checkpoint.v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "config_sha256": file_sha256(config.path),
        "input_sha256": file_sha256(input_path),
        "workflow": workflow,
        "strategy": strategy,
        "dry_run": dry_run,
        "verify": verify,
        "model": model,
        "total_problems": total_problems,
    }
    checkpoint_meta_path(trace_dir).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def verify_checkpoint_meta(
    trace_dir: Path,
    *,
    config: HarnessConfig,
    input_path: Path,
    workflow: str | None,
    strategy: str,
    dry_run: bool,
    verify: bool,
    model: str,
    total_problems: int,
) -> None:
    path = checkpoint_meta_path(trace_dir)
    if not path.exists():
        return
    meta = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "config_sha256": file_sha256(config.path),
        "input_sha256": file_sha256(input_path),
        "workflow": workflow,
        "strategy": strategy,
        "dry_run": dry_run,
        "verify": verify,
        "model": model,
        "total_problems": total_problems,
    }
    mismatches = [
        key for key, expected_value in expected.items() if meta.get(key) != expected_value
    ]
    if mismatches:
        joined = ", ".join(mismatches)
        raise ValueError(f"Checkpoint does not match this run: {joined}")


def append_checkpoint(trace_dir: Path, predictions: list[Prediction]) -> None:
    if not predictions:
        return
    trace_dir.mkdir(parents=True, exist_ok=True)
    with checkpoint_path(trace_dir).open("a", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(asdict(prediction), ensure_ascii=False) + "\n")


def write_checkpoint(trace_dir: Path, predictions: list[Prediction]) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    with checkpoint_path(trace_dir).open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(asdict(prediction), ensure_ascii=False) + "\n")


def load_checkpoint(trace_dir: Path) -> dict[str, Prediction]:
    path = checkpoint_path(trace_dir)
    if not path.exists():
        return {}
    predictions: dict[str, Prediction] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            prediction = _prediction_from_dict(json.loads(stripped))
            predictions[prediction.qid] = prediction
    return predictions


def _prediction_from_dict(row: dict[str, Any]) -> Prediction:
    trace = tuple(_trace_step_from_dict(item) for item in row.get("trace", ()))
    return Prediction(
        qid=str(row["qid"]),
        answer=str(row["answer"]),
        model=str(row["model"]),
        raw_answer=str(row["raw_answer"]),
        strategy=str(row["strategy"]),
        confidence=float(row["confidence"]),
        question_kind=str(row.get("question_kind", "general")),
        prompt_variant=str(row.get("prompt_variant", "direct")),
        attempts=int(row.get("attempts", 1)),
        fallback_reason=_optional_string(row.get("fallback_reason")),
        trace=trace,
    )


def _trace_step_from_dict(row: dict[str, Any]) -> TraceStep:
    return TraceStep(
        role=str(row["role"]),
        action=str(row["action"]),
        status=str(row["status"]),
        detail=str(row["detail"]),
        answer=_optional_string(row.get("answer")),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
