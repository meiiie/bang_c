from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .review import ReviewFinding, TraceReview


@dataclass(frozen=True)
class ReviewTask:
    task_id: str
    priority: str
    qid: str | None
    finding_code: str
    title: str
    recommended_action: str


def build_review_tasks(review: TraceReview) -> tuple[ReviewTask, ...]:
    tasks: list[ReviewTask] = []
    for index, finding in enumerate(review.findings, start=1):
        if finding.severity == "info":
            continue
        tasks.append(_task_from_finding(finding, index=index))
    return tuple(tasks)


def render_review_tasks(tasks: tuple[ReviewTask, ...]) -> str:
    lines = [
        "Neko Core Review Tasks",
        f"Tasks: {len(tasks)}",
        "",
    ]
    if not tasks:
        lines.append("- none")
        return "\n".join(lines)

    for task in tasks:
        qid = f" [{task.qid}]" if task.qid else ""
        lines.append(f"- {task.priority.upper()} {task.task_id}{qid}: {task.title}")
        lines.append(f"  Action: {task.recommended_action}")
    return "\n".join(lines)


def write_review_tasks_json(path: Path, tasks: tuple[ReviewTask, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "neko_core.review_tasks.v1",
        "tasks": [asdict(task) for task in tasks],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_review_tasks_markdown(path: Path, tasks: tuple[ReviewTask, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_review_tasks(tasks) + "\n", encoding="utf-8")


def _task_from_finding(finding: ReviewFinding, *, index: int) -> ReviewTask:
    priority = _priority(finding)
    target = finding.qid or "run"
    task_id = f"{index:03d}-{_slug(target)}-{_slug(finding.code)}"
    return ReviewTask(
        task_id=task_id,
        priority=priority,
        qid=finding.qid,
        finding_code=finding.code,
        title=_title(finding),
        recommended_action=_recommended_action(finding),
    )


def _priority(finding: ReviewFinding) -> str:
    if finding.severity == "fail":
        return "high"
    if finding.code in {"risk_agent_disagreement", "risk_tournament_tie"}:
        return "medium"
    if finding.code in {"fallback_path", "trace_warning", "low_confidence"}:
        return "medium"
    return "low"


def _title(finding: ReviewFinding) -> str:
    if finding.qid:
        return f"Review {finding.qid} because {finding.code} was reported."
    return f"Review run-level issue {finding.code}."


def _recommended_action(finding: ReviewFinding) -> str:
    if finding.code == "low_confidence":
        return "Rerun this item with verify or tournament and inspect prompt evidence."
    if finding.code == "fallback_path":
        return "Inspect the raw model output and input shape before changing prompts."
    if finding.code == "trace_warning":
        return "Compare solver, repair, verifier, and synthesizer steps for drift."
    if finding.code == "risk_agent_disagreement":
        return "Inspect competing answers in the trace and rerun with a focused adjudicator."
    if finding.code == "risk_tournament_tie":
        return "Inspect the tie-breaker and verifier prompts before trusting the selected answer."
    if finding.code == "risk_broad_marker_ignored":
        return "Confirm the ignored broad marker is not the real task type before changing classifier rules."
    if finding.code.startswith("risk_compound_"):
        return "Check whether the selected strategy covered every detected task feature."
    if finding.code == "risk_quality_low_confidence":
        return "Queue for human or stronger-model review if this item affects leaderboard accuracy."
    if finding.code in {"trace_blocked", "invalid_contract", "trace_count_mismatch"}:
        return "Fix the contract or blocked trace before trusting this run."
    if finding.code in {"missing_summary", "missing_trace", "missing_manifest"}:
        return "Regenerate the run with --trace-dir or --run-dir enabled."
    return "Inspect the trace and decide whether config, classifier, or strategy should change."


def _slug(value: str) -> str:
    lowered = value.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "item"
