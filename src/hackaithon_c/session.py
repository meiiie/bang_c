from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evaluation import RunSummary
from .review import TraceReview, review_trace_dir


@dataclass(frozen=True)
class RunSession:
    run_dir: Path
    output_dir: Path
    trace_dir: Path
    report_path: Path
    review_tasks_json_path: Path
    review_tasks_markdown_path: Path
    events_path: Path


@dataclass(frozen=True)
class RunSessionRecord:
    run_dir: Path
    updated_at_utc: str
    workflow: str
    strategy: str
    model: str
    input_path: str
    output_path: str
    trace_dir: Path
    valid: bool | None
    total_problems: int | None
    total_predictions: int | None
    average_confidence: float | None
    review_verdict: str
    review_task_count: int
    review_tasks_path: Path
    event_count: int
    events_path: Path


def prepare_run_session(
    run_dir: Path,
    *,
    output_dir: Path | None = None,
    trace_dir: Path | None = None,
) -> RunSession:
    return RunSession(
        run_dir=run_dir,
        output_dir=output_dir or run_dir / "output",
        trace_dir=trace_dir or run_dir / "traces",
        report_path=run_dir / "run-report.md",
        review_tasks_json_path=run_dir / "review-tasks.json",
        review_tasks_markdown_path=run_dir / "review-tasks.md",
        events_path=run_dir / "events.jsonl",
    )


def discover_run_sessions(root: Path, *, max_depth: int = 3) -> tuple[RunSessionRecord, ...]:
    records: list[RunSessionRecord] = []
    for run_dir in _candidate_run_dirs(root, max_depth=max_depth):
        record = load_run_session_record(run_dir)
        if record is not None:
            records.append(record)
    return tuple(sorted(records, key=lambda record: record.updated_at_utc, reverse=True))


def load_run_session_record(run_dir: Path) -> RunSessionRecord | None:
    report_path = run_dir / "run-report.md"
    if not report_path.exists():
        return None

    default_trace_dir = run_dir / "traces"
    manifest = _read_json(default_trace_dir / "run-manifest.json")
    trace_dir = Path(str(manifest.get("trace_dir", default_trace_dir))) if manifest else default_trace_dir
    summary = _read_json(trace_dir / "run-summary.json")
    review_tasks_path = run_dir / "review-tasks.json"
    review_tasks = _read_json(review_tasks_path)
    events_path = run_dir / "events.jsonl"
    review = review_trace_dir(trace_dir) if trace_dir.exists() else None

    stat = report_path.stat()
    updated_at_utc = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds")
    return RunSessionRecord(
        run_dir=run_dir,
        updated_at_utc=updated_at_utc,
        workflow=str(_get(manifest, "workflow", "unknown")),
        strategy=str(_get(manifest, "strategy", "unknown")),
        model=str(_get(manifest, "model", "unknown")),
        input_path=str(_get(manifest, "input_path", "")),
        output_path=str(_get(manifest, "output_path", run_dir / "output" / "pred.csv")),
        trace_dir=trace_dir,
        valid=_optional_bool(summary.get("valid")) if summary else None,
        total_problems=_optional_int(summary.get("total_problems")) if summary else None,
        total_predictions=_optional_int(summary.get("total_predictions")) if summary else None,
        average_confidence=_optional_float(summary.get("average_confidence")) if summary else None,
        review_verdict=review.verdict if review else "missing",
        review_task_count=_task_count(review_tasks),
        review_tasks_path=review_tasks_path,
        event_count=_event_count(events_path),
        events_path=events_path,
    )


def render_run_sessions(
    records: tuple[RunSessionRecord, ...],
    *,
    root: Path,
) -> str:
    lines = [
        "Neko Core Run Sessions",
        f"Root: {root}",
        f"Sessions: {len(records)}",
        "",
    ]
    if not records:
        lines.append("- none")
        return "\n".join(lines)

    for record in records:
        predictions = _predictions_label(record)
        lines.append(
            "- "
            f"{record.run_dir} | {record.workflow} | {record.model} | "
            f"valid={record.valid} | predictions={predictions} | "
            f"review={record.review_verdict.upper()} | tasks={record.review_task_count} | "
            f"events={record.event_count} | "
            f"updated={record.updated_at_utc}"
        )
    return "\n".join(lines)


def render_run_session_detail(record: RunSessionRecord) -> str:
    lines = [
        "Neko Core Session",
        f"Run: {record.run_dir}",
        f"Updated: {record.updated_at_utc}",
        f"Workflow: {record.workflow}",
        f"Strategy: {record.strategy}",
        f"Model: {record.model}",
        f"Input: {record.input_path or 'unknown'}",
        f"Output: {record.output_path}",
        f"Trace: {record.trace_dir}",
        f"Valid: {record.valid}",
        f"Predictions: {_predictions_label(record)}",
        f"Average confidence: {_none_label(record.average_confidence)}",
        f"Trace review: {record.review_verdict.upper()}",
        f"Review tasks: {record.review_task_count}",
        f"Events: {record.event_count}",
        "",
        "Next commands:",
        f"- Review: neko --review-trace \"{record.trace_dir}\"",
        f"- Events: neko --events \"{record.run_dir}\"",
    ]
    if record.review_tasks_path.exists() and record.input_path:
        lines.append(
            "- Resolve: "
            f".\\scripts\\resolve-tasks.ps1 -TaskPath \"{record.review_tasks_path}\" "
            f"-InputPath \"{record.input_path}\" -Workflow verify-all"
        )
    elif record.review_task_count == 0:
        lines.append("- Resolve: no review tasks found")
    else:
        lines.append("- Resolve: missing review task file or input path")
    return "\n".join(lines)


def write_run_report(
    path: Path,
    *,
    input_path: Path,
    output_path: Path,
    trace_dir: Path,
    workflow: str | None,
    strategy: str,
    dry_run: bool,
    verify: bool,
    model: str,
    summary: RunSummary,
    review: TraceReview | None = None,
    review_tasks_path: Path | None = None,
) -> None:
    lines = [
        "# Neko Core Run Report",
        "",
        f"- Input: {input_path}",
        f"- Output: {output_path}",
        f"- Trace: {trace_dir}",
        f"- Workflow: {workflow or 'ad hoc'}",
        f"- Strategy: {strategy}",
        f"- Dry run: {dry_run}",
        f"- Verify: {verify}",
        f"- Model: {model}",
        f"- Valid: {summary.valid}",
        f"- Predictions: {summary.total_predictions}/{summary.total_problems}",
        f"- Average confidence: {summary.average_confidence}",
        f"- Fallbacks: {summary.fallbacks}",
        f"- Harness score: {summary.harness_score.get('total', 0)}",
        "",
        "## Strategy Counts",
        "",
    ]
    for name, count in summary.strategies.items():
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Question Kinds", ""])
    for name, count in summary.question_kinds.items():
        lines.append(f"- {name}: {count}")

    if review is not None:
        lines.extend(
            [
                "",
                "## Trace Review",
                "",
                f"- Verdict: {review.verdict.upper()}",
                f"- Findings: {len(review.findings)}",
            ]
        )
        if review_tasks_path is not None:
            lines.append(f"- Review tasks: {review_tasks_path}")
        for finding in review.findings[:10]:
            qid = f" [{finding.qid}]" if finding.qid else ""
            lines.append(
                f"- {finding.severity.upper()} "
                f"{finding.code}{qid}: {finding.message}"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_run_dirs(root: Path, *, max_depth: int) -> tuple[Path, ...]:
    root = Path(root)
    if not root.exists():
        return ()

    candidates: list[Path] = []
    seen: set[Path] = set()
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        resolved = current.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (current / "run-report.md").exists():
            candidates.append(current)
            continue
        if depth >= max_depth:
            continue
        for child in _safe_iter_dirs(current):
            if _skip_scan_dir(child):
                continue
            stack.append((child, depth + 1))
    return tuple(candidates)


def _safe_iter_dirs(path: Path) -> tuple[Path, ...]:
    try:
        return tuple(child for child in path.iterdir() if child.is_dir())
    except OSError:
        return ()


def _skip_scan_dir(path: Path) -> bool:
    name = path.name
    return (
        name in {".git", ".venv", "__pycache__", "src", "tests", "docs", "configs"}
        or name.startswith("output")
        or name.startswith("traces")
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return value


def _get(payload: dict[str, Any] | None, key: str, default: Any) -> Any:
    if payload is None:
        return default
    value = payload.get(key)
    return default if value is None else value


def _task_count(payload: dict[str, Any] | None) -> int:
    if payload is None:
        return 0
    tasks = payload.get("tasks", [])
    return len(tasks) if isinstance(tasks, list) else 0


def _event_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _predictions_label(record: RunSessionRecord) -> str:
    if record.total_predictions is None or record.total_problems is None:
        return "unknown"
    return f"{record.total_predictions}/{record.total_problems}"


def _none_label(value: object | None) -> str:
    return "unknown" if value is None else str(value)
