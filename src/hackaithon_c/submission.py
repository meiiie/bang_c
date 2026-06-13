from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .config import HarnessConfig
from .schema import Problem


@dataclass(frozen=True)
class SubmissionIssue:
    code: str
    message: str
    qid: str | None = None


@dataclass(frozen=True)
class SubmissionCheck:
    path: Path
    valid: bool
    input_rows: int
    prediction_rows: int
    issues: tuple[SubmissionIssue, ...]


def check_submission_file(
    path: Path,
    problems: list[Problem],
    config: HarnessConfig,
) -> SubmissionCheck:
    issues: list[SubmissionIssue] = []
    if path.name != config.output_file:
        issues.append(
            SubmissionIssue(
                "wrong_file_name",
                f"Submission file must be named {config.output_file}, got {path.name}",
            )
        )
    if not path.exists():
        return SubmissionCheck(
            path=path,
            valid=False,
            input_rows=len(problems),
            prediction_rows=0,
            issues=tuple(
                issues
                + [
                    SubmissionIssue(
                        "missing_file",
                        f"Submission file not found: {path}",
                    )
                ]
            ),
        )

    raw = path.read_bytes()
    issues.extend(_strict_raw_csv_issues(raw, config))

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames != config.output_columns:
            issues.append(
                SubmissionIssue(
                    "invalid_header",
                    f"Header must be {','.join(config.output_columns)}, got {','.join(fieldnames)}",
                )
            )
        for row in reader:
            rows.append({str(key): str(value).strip() for key, value in row.items()})

    by_qid = {problem.qid: problem for problem in problems}
    seen: set[str] = set()
    for row in rows:
        qid = row.get("qid", "")
        answer = row.get("answer", "").upper()
        if not qid:
            issues.append(SubmissionIssue("missing_qid", "Prediction row has no qid"))
            continue
        if qid in seen:
            issues.append(SubmissionIssue("duplicate_qid", "Duplicate prediction qid", qid))
        seen.add(qid)
        problem = by_qid.get(qid)
        if problem is None:
            issues.append(SubmissionIssue("extra_qid", "Prediction qid is not in input", qid))
            continue
        if answer not in problem.allowed_letters:
            issues.append(
                SubmissionIssue(
                    "invalid_answer",
                    f"Answer {answer!r} is not in allowed letters {problem.allowed_letters}",
                    qid,
                )
            )

    for qid in sorted(set(by_qid) - seen):
        issues.append(SubmissionIssue("missing_prediction", "Missing prediction", qid))

    return SubmissionCheck(
        path=path,
        valid=not issues,
        input_rows=len(problems),
        prediction_rows=len(rows),
        issues=tuple(issues),
    )


def _strict_raw_csv_issues(
    raw: bytes,
    config: HarnessConfig,
) -> list[SubmissionIssue]:
    issues: list[SubmissionIssue] = []
    expected_header = ",".join(config.output_columns).encode("ascii")
    raw_lines = raw.splitlines()
    first_line = raw_lines[0] if raw_lines else b""
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(
            SubmissionIssue(
                "utf8_bom",
                "Submission CSV must be UTF-8 without BOM",
            )
        )
    if first_line != expected_header:
        issues.append(
            SubmissionIssue(
                "invalid_raw_header",
                (
                    f"Raw header must be {expected_header.decode('ascii')}, got "
                    f"{first_line.decode('utf-8', errors='replace')}"
                ),
            )
        )
    if b'"' in raw:
        issues.append(
            SubmissionIssue(
                "quoted_csv",
                "Submission CSV must use bare qid,answer rows; do not export with quoted fields",
            )
        )
    return issues


def render_submission_check(check: SubmissionCheck) -> str:
    lines = [
        "Neko Core submission check",
        f"File: {check.path}",
        f"Valid: {check.valid}",
        f"Input rows: {check.input_rows}",
        f"Prediction rows: {check.prediction_rows}",
    ]
    if not check.issues:
        lines.append("Issues: none")
        return "\n".join(lines)
    lines.append(f"Issues: {len(check.issues)}")
    for issue in check.issues[:20]:
        qid = f" [{issue.qid}]" if issue.qid else ""
        lines.append(f"- {issue.code}{qid}: {issue.message}")
    if len(check.issues) > 20:
        lines.append(f"- ... {len(check.issues) - 20} more")
    return "\n".join(lines)
