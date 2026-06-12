from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import HarnessConfig
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
    harness_score: dict[str, float]


def validate_predictions(
    problems: list[Problem],
    predictions: list[Prediction],
    config: HarnessConfig,
    *,
    trace_enabled: bool = False,
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
    fallbacks = sum(1 for prediction in predictions if prediction.fallback_reason)
    base = RunSummary(
        total_problems=len(problems),
        total_predictions=len(predictions),
        valid=not issues,
        issues=tuple(issues),
        strategies=dict(sorted(strategies.items())),
        question_kinds=dict(sorted(question_kinds.items())),
        fallbacks=fallbacks,
        average_confidence=average_confidence,
        harness_score={},
    )
    return RunSummary(
        total_problems=base.total_problems,
        total_predictions=base.total_predictions,
        valid=base.valid,
        issues=base.issues,
        strategies=base.strategies,
        question_kinds=base.question_kinds,
        fallbacks=base.fallbacks,
        average_confidence=base.average_confidence,
        harness_score=score_harness(base, config, trace_enabled=trace_enabled),
    )


def repair_predictions_for_contract(
    problems: list[Problem],
    predictions: list[Prediction],
) -> list[Prediction]:
    """Return predictions covering exactly the input qids, in input order, each
    carrying a letter valid for its own problem.

    Existing good predictions are kept verbatim, so accuracy is never lowered. A
    missing qid, an out-of-range letter, or a duplicate is replaced by a
    deterministic heuristic fallback. This guarantees a contract-valid pred.csv can
    always be written: a single solver gap can never zero the whole submission.
    """
    from .heuristic import fallback_answer

    by_qid: dict[str, Prediction] = {}
    for prediction in predictions:
        by_qid.setdefault(prediction.qid, prediction)  # first occurrence wins; drops dupes

    repaired: list[Prediction] = []
    for problem in problems:
        existing = by_qid.get(problem.qid)
        if existing is not None and existing.answer in problem.allowed_letters:
            repaired.append(existing)
            continue
        answer, confidence, strategy = fallback_answer(problem)
        repaired.append(
            Prediction(
                qid=problem.qid,
                answer=answer,
                model=existing.model if existing else "heuristic",
                raw_answer=existing.raw_answer if existing else answer,
                strategy=f"{strategy}_contract_repair",
                confidence=confidence,
                question_kind=existing.question_kind if existing else "general",
                prompt_variant=existing.prompt_variant if existing else "heuristic",
                fallback_reason=(existing.fallback_reason if existing else None)
                or "contract_repair",
            )
        )
    return repaired


def score_harness(
    summary: RunSummary,
    config: HarnessConfig,
    *,
    trace_enabled: bool,
) -> dict[str, float]:
    weights = config.rubric
    contract = float(weights["contract"] if summary.valid else 0)
    reproducibility = float(weights["reproducibility"])
    fallback_ratio = summary.fallbacks / max(1, summary.total_predictions)
    robustness = float(weights["robustness"] * max(0.0, 1.0 - fallback_ratio))
    runtime_discipline = float(weights["runtime_discipline"])
    traceability = float(weights["traceability"] if trace_enabled else 0)
    total = contract + reproducibility + robustness + runtime_discipline + traceability
    return {
        "total": round(total, 2),
        "contract": round(contract, 2),
        "reproducibility": round(reproducibility, 2),
        "robustness": round(robustness, 2),
        "runtime_discipline": round(runtime_discipline, 2),
        "traceability": round(traceability, 2),
    }


def write_summary(path: Path, summary: RunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
