from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .schema import Prediction, Problem


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    qid: str | None = None


@dataclass(frozen=True)
class RunSummary:
    total_problems: int
    total_predictions: int
    valid: bool
    issues: tuple[ValidationIssue, ...]
    strategies: dict[str, int]
    question_kinds: dict[str, int]
    fallbacks: int
    average_confidence: float


def validate_predictions(
    problems: list[Problem],
    predictions: list[Prediction],
) -> RunSummary:
    issues: list[ValidationIssue] = []
    problem_by_qid = {problem.qid: problem for problem in problems}
    if len(problem_by_qid) != len(problems):
        issues.append(ValidationIssue("duplicate_input_qid", "Input contains duplicate qid"))

    prediction_qids = [prediction.qid for prediction in predictions]
    duplicate_predictions = [
        qid for qid, count in Counter(prediction_qids).items() if count > 1
    ]
    for qid in duplicate_predictions:
        issues.append(ValidationIssue("duplicate_prediction_qid", "Duplicate prediction qid", qid))

    missing = sorted(set(problem_by_qid) - set(prediction_qids))
    for qid in missing:
        issues.append(ValidationIssue("missing_prediction", "Missing prediction", qid))

    extra = sorted(set(prediction_qids) - set(problem_by_qid))
    for qid in extra:
        issues.append(ValidationIssue("extra_prediction", "Prediction qid not in input", qid))

    for prediction in predictions:
        problem = problem_by_qid.get(prediction.qid)
        if problem is None:
            continue
        if prediction.answer not in problem.allowed_letters:
            issues.append(
                ValidationIssue(
                    "invalid_answer_letter",
                    f"Answer {prediction.answer!r} not in {problem.allowed_letters}",
                    prediction.qid,
                )
            )

    strategies = Counter(prediction.strategy for prediction in predictions)
    question_kinds = Counter(prediction.question_kind for prediction in predictions)
    average_confidence = 0.0
    if predictions:
        average_confidence = round(
            sum(prediction.confidence for prediction in predictions) / len(predictions),
            4,
        )
    return RunSummary(
        total_problems=len(problems),
        total_predictions=len(predictions),
        valid=not issues,
        issues=tuple(issues),
        strategies=dict(sorted(strategies.items())),
        question_kinds=dict(sorted(question_kinds.items())),
        fallbacks=sum(1 for prediction in predictions if prediction.fallback_reason),
        average_confidence=average_confidence,
    )


def write_summary(path: Path, summary: RunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
