from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .evaluation import RunSummary
from .review import TraceReview


@dataclass(frozen=True)
class RunSession:
    run_dir: Path
    output_dir: Path
    trace_dir: Path
    report_path: Path
    review_tasks_json_path: Path
    review_tasks_markdown_path: Path


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
    )


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
