from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


Severity = Literal["info", "warn", "fail"]
Verdict = Literal["pass", "warn", "fail"]


@dataclass(frozen=True)
class CompareFinding:
    severity: Severity
    code: str
    message: str
    qid: str | None = None


@dataclass(frozen=True)
class TraceComparison:
    left_dir: str
    right_dir: str
    verdict: Verdict
    left_predictions: int
    right_predictions: int
    changed_answers: int
    findings: tuple[CompareFinding, ...]


def compare_trace_dirs(
    left_dir: Path,
    right_dir: Path,
    *,
    qids: tuple[str, ...] = (),
) -> TraceComparison:
    findings: list[CompareFinding] = []
    selected_qids = _dedupe_qids(qids)
    left = _load_bundle(left_dir, findings, side="left", qids=selected_qids)
    right = _load_bundle(right_dir, findings, side="right", qids=selected_qids)
    if left is None or right is None:
        return _comparison(
            left_dir,
            right_dir,
            findings,
            left_predictions=0,
            right_predictions=0,
            changed_answers=0,
        )

    _compare_manifests(left["manifest"], right["manifest"], findings)
    changed_answers = _compare_predictions(
        left["predictions"],
        right["predictions"],
        findings,
    )

    if not findings:
        findings.append(
            CompareFinding(
                severity="info",
                code="trace_match",
                message="No prediction or manifest differences found.",
            )
        )

    return _comparison(
        left_dir,
        right_dir,
        findings,
        left_predictions=len(left["predictions"]),
        right_predictions=len(right["predictions"]),
        changed_answers=changed_answers,
    )


def render_trace_comparison(comparison: TraceComparison) -> str:
    lines = [
        "Neko Core Trace Comparison",
        f"Left: {comparison.left_dir}",
        f"Right: {comparison.right_dir}",
        f"Verdict: {comparison.verdict.upper()}",
        f"Predictions: {comparison.left_predictions} -> {comparison.right_predictions}",
        f"Changed answers: {comparison.changed_answers}",
        "",
        "Findings:",
    ]
    for finding in comparison.findings:
        qid = f" [{finding.qid}]" if finding.qid else ""
        lines.append(f"- {finding.severity.upper()} {finding.code}{qid}: {finding.message}")
    return "\n".join(lines)


def _load_bundle(
    trace_dir: Path,
    findings: list[CompareFinding],
    *,
    side: str,
    qids: tuple[str, ...],
) -> dict[str, Any] | None:
    trace_path = trace_dir / "predictions.trace.jsonl"
    summary_path = trace_dir / "run-summary.json"
    manifest_path = trace_dir / "run-manifest.json"
    failed = False

    if not trace_path.exists():
        findings.append(
            CompareFinding(
                severity="fail",
                code=f"{side}_missing_trace",
                message=f"Missing prediction trace: {trace_path}",
            )
        )
        failed = True
    if not summary_path.exists():
        findings.append(
            CompareFinding(
                severity="fail",
                code=f"{side}_missing_summary",
                message=f"Missing run summary: {summary_path}",
            )
        )
        failed = True
    if failed:
        return None

    predictions = _read_trace_jsonl(trace_path)
    summary = _read_json(summary_path)
    manifest = _read_json(manifest_path) if manifest_path.exists() else None
    if manifest is None:
        findings.append(
            CompareFinding(
                severity="warn",
                code=f"{side}_missing_manifest",
                message=f"Missing run manifest: {manifest_path}",
            )
        )

    if int(summary.get("total_predictions", 0)) != len(predictions):
        findings.append(
            CompareFinding(
                severity="fail",
                code=f"{side}_trace_count_mismatch",
                message="Trace row count does not match run summary.",
            )
        )

    prediction_map = {str(row.get("qid")): row for row in predictions}
    if qids:
        for qid in qids:
            if qid not in prediction_map:
                findings.append(
                    CompareFinding(
                        severity="fail",
                        code=f"{side}_missing_selected_qid",
                        message="Selected qid is not present in this trace.",
                        qid=qid,
                    )
                )
        prediction_map = {qid: prediction_map[qid] for qid in qids if qid in prediction_map}

    return {
        "predictions": prediction_map,
        "summary": summary,
        "manifest": manifest,
    }


def _compare_manifests(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    findings: list[CompareFinding],
) -> None:
    if left is None or right is None:
        return
    for field in ("input_sha256", "config_sha256"):
        if left.get(field) != right.get(field):
            findings.append(
                CompareFinding(
                    severity="warn",
                    code=f"{field}_changed",
                    message=f"{field} differs between runs.",
                )
            )
    for field in ("workflow", "strategy", "model"):
        if left.get(field) != right.get(field):
            findings.append(
                CompareFinding(
                    severity="info",
                    code=f"{field}_changed",
                    message=f"{field}: {left.get(field)} -> {right.get(field)}",
                )
            )


def _compare_predictions(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
    findings: list[CompareFinding],
) -> int:
    left_qids = set(left)
    right_qids = set(right)
    missing = sorted(left_qids - right_qids)
    extra = sorted(right_qids - left_qids)
    for qid in missing:
        findings.append(
            CompareFinding(
                severity="fail",
                code="missing_prediction",
                message="Prediction exists in left run but not right run.",
                qid=qid,
            )
        )
    for qid in extra:
        findings.append(
            CompareFinding(
                severity="fail",
                code="extra_prediction",
                message="Prediction exists in right run but not left run.",
                qid=qid,
            )
        )

    changed_answers = 0
    for qid in sorted(left_qids & right_qids):
        left_row = left[qid]
        right_row = right[qid]
        if str(left_row.get("answer")) != str(right_row.get("answer")):
            changed_answers += 1
            findings.append(
                CompareFinding(
                    severity="warn",
                    code="answer_changed",
                    message=f"{left_row.get('answer')} -> {right_row.get('answer')}",
                    qid=qid,
                )
            )

        confidence_delta = abs(
            float(left_row.get("confidence", 0.0))
            - float(right_row.get("confidence", 0.0))
        )
        if confidence_delta >= 0.25:
            findings.append(
                CompareFinding(
                    severity="warn",
                    code="confidence_changed",
                    message=f"Confidence delta is {confidence_delta:.4f}.",
                    qid=qid,
                )
            )

        left_fallback = bool(left_row.get("fallback_reason"))
        right_fallback = bool(right_row.get("fallback_reason"))
        if left_fallback != right_fallback:
            findings.append(
                CompareFinding(
                    severity="warn",
                    code="fallback_changed",
                    message=f"fallback={left_fallback} -> {right_fallback}",
                    qid=qid,
                )
            )
    return changed_answers


def _comparison(
    left_dir: Path,
    right_dir: Path,
    findings: list[CompareFinding],
    *,
    left_predictions: int,
    right_predictions: int,
    changed_answers: int,
) -> TraceComparison:
    verdict: Verdict = "pass"
    if any(finding.severity == "fail" for finding in findings):
        verdict = "fail"
    elif any(finding.severity == "warn" for finding in findings):
        verdict = "warn"
    return TraceComparison(
        left_dir=str(left_dir),
        right_dir=str(right_dir),
        verdict=verdict,
        left_predictions=left_predictions,
        right_predictions=right_predictions,
        changed_answers=changed_answers,
        findings=tuple(findings),
    )


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


def _dedupe_qids(qids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(qid.strip() for qid in qids if qid.strip()))
