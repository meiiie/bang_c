from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .risk import collect_prediction_risks


Severity = Literal["info", "warn", "fail"]
Verdict = Literal["pass", "warn", "fail"]


@dataclass(frozen=True)
class ReviewFinding:
    severity: Severity
    code: str
    message: str
    qid: str | None = None


@dataclass(frozen=True)
class TraceReview:
    trace_dir: str
    verdict: Verdict
    total_predictions: int
    findings: tuple[ReviewFinding, ...]


def review_trace_dir(trace_dir: Path, *, low_confidence_threshold: float = 0.5) -> TraceReview:
    summary_path = trace_dir / "run-summary.json"
    trace_path = trace_dir / "predictions.trace.jsonl"
    manifest_path = trace_dir / "run-manifest.json"
    findings: list[ReviewFinding] = []

    if not summary_path.exists():
        findings.append(
            ReviewFinding(
                severity="fail",
                code="missing_summary",
                message=f"Missing run summary: {summary_path}",
            )
        )
    if not trace_path.exists():
        findings.append(
            ReviewFinding(
                severity="fail",
                code="missing_trace",
                message=f"Missing prediction trace: {trace_path}",
            )
        )

    if findings:
        return _review(trace_dir, findings, total_predictions=0)

    summary = _read_json(summary_path)
    predictions = _read_trace_jsonl(trace_path)
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        if manifest.get("schema_version") != "neko_core.run_manifest.v1":
            findings.append(
                ReviewFinding(
                    severity="fail",
                    code="invalid_manifest_schema",
                    message="Run manifest schema is not supported.",
                )
            )
        if int(manifest.get("total_predictions", -1)) != int(
            summary.get("total_predictions", 0)
        ):
            findings.append(
                ReviewFinding(
                    severity="fail",
                    code="manifest_count_mismatch",
                    message="Run manifest prediction count does not match run summary.",
                )
            )
        if len(str(manifest.get("input_sha256", ""))) != 64:
            findings.append(
                ReviewFinding(
                    severity="warn",
                    code="manifest_missing_input_hash",
                    message="Run manifest does not include a valid input hash.",
                )
            )
    else:
        findings.append(
            ReviewFinding(
                severity="warn",
                code="missing_manifest",
                message=f"Missing run manifest: {manifest_path}",
            )
        )

    if not bool(summary.get("valid", False)):
        findings.append(
            ReviewFinding(
                severity="fail",
                code="invalid_contract",
                message="Run summary reports an invalid prediction contract.",
            )
        )

    if int(summary.get("total_predictions", 0)) != len(predictions):
        findings.append(
            ReviewFinding(
                severity="fail",
                code="trace_count_mismatch",
                message=(
                    "Trace row count does not match run summary "
                    f"({len(predictions)} != {summary.get('total_predictions')})."
                ),
            )
        )

    for prediction in predictions:
        qid = _string_or_none(prediction.get("qid"))
        confidence = float(prediction.get("confidence", 0.0))
        strategy = str(prediction.get("strategy", ""))
        fallback_reason = prediction.get("fallback_reason")
        trace_steps = prediction.get("trace", [])

        if confidence < low_confidence_threshold:
            findings.append(
                ReviewFinding(
                    severity="warn",
                    code="low_confidence",
                    message=f"Confidence {confidence:.4f} is below {low_confidence_threshold:.2f}.",
                    qid=qid,
                )
            )

        if fallback_reason or "_after_" in strategy:
            findings.append(
                ReviewFinding(
                    severity="warn",
                    code="fallback_path",
                    message=f"Prediction used fallback path: {fallback_reason or strategy}.",
                    qid=qid,
                )
            )

        findings.extend(_review_trace_steps(qid, trace_steps))
        for signal in collect_prediction_risks(prediction):
            findings.append(
                ReviewFinding(
                    severity=signal.severity,
                    code=f"risk_{signal.code}",
                    message=signal.message,
                    qid=qid,
                )
            )

    if not findings:
        findings.append(
            ReviewFinding(
                severity="info",
                code="trace_clean",
                message="No trace issues found.",
            )
        )

    return _review(trace_dir, findings, total_predictions=len(predictions))


def render_trace_review(review: TraceReview) -> str:
    lines = [
        "Neko Core Trace Review",
        f"Trace directory: {review.trace_dir}",
        f"Verdict: {review.verdict.upper()}",
        f"Predictions reviewed: {review.total_predictions}",
        "",
        "Findings:",
    ]
    for finding in review.findings:
        qid = f" [{finding.qid}]" if finding.qid else ""
        lines.append(f"- {finding.severity.upper()} {finding.code}{qid}: {finding.message}")
    return "\n".join(lines)


def _review(
    trace_dir: Path,
    findings: list[ReviewFinding],
    *,
    total_predictions: int,
) -> TraceReview:
    verdict: Verdict = "pass"
    if any(finding.severity == "fail" for finding in findings):
        verdict = "fail"
    elif any(finding.severity == "warn" for finding in findings):
        verdict = "warn"
    return TraceReview(
        trace_dir=str(trace_dir),
        verdict=verdict,
        total_predictions=total_predictions,
        findings=tuple(findings),
    )


def _review_trace_steps(qid: str | None, trace_steps: Any) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    if not isinstance(trace_steps, list) or not trace_steps:
        return [
            ReviewFinding(
                severity="warn",
                code="missing_agent_trace",
                message="Prediction has no structured trace steps.",
                qid=qid,
            )
        ]

    roles = [str(step.get("role", "")) for step in trace_steps if isinstance(step, dict)]
    if "classifier" not in roles:
        findings.append(
            ReviewFinding(
                severity="warn",
                code="missing_classifier_step",
                message="Trace does not include a classifier step.",
                qid=qid,
            )
        )
    if "solver" not in roles:
        findings.append(
            ReviewFinding(
                severity="warn",
                code="missing_solver_step",
                message="Trace does not include a solver step.",
                qid=qid,
            )
        )

    for step in trace_steps:
        if not isinstance(step, dict):
            continue
        status = str(step.get("status", ""))
        action = str(step.get("action", "unknown"))
        if status == "warning":
            findings.append(
                ReviewFinding(
                    severity="warn",
                    code="trace_warning",
                    message=f"Trace step warned during {action}.",
                    qid=qid,
                )
            )
        if status in {"blocked", "failed"}:
            findings.append(
                ReviewFinding(
                    severity="fail",
                    code="trace_blocked",
                    message=f"Trace step {status} during {action}.",
                    qid=qid,
                )
            )
    return findings


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return value


def _read_trace_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected object JSONL row in {path}")
        rows.append(value)
    return rows


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
