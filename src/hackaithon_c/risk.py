from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


RiskSeverity = Literal["info", "warn"]


@dataclass(frozen=True)
class RiskSignal:
    severity: RiskSeverity
    code: str
    message: str


def collect_prediction_risks(
    prediction: dict[str, Any],
    *,
    quality_confidence_threshold: float = 0.84,
) -> tuple[RiskSignal, ...]:
    trace_steps = prediction.get("trace", [])
    if not isinstance(trace_steps, list):
        return ()

    signals: list[RiskSignal] = []
    classifier_detail = _classifier_detail(trace_steps)
    features = _parse_detail_list(classifier_detail, "features")
    diagnostics = _parse_detail_list(classifier_detail, "diagnostics")

    if _has_solver_disagreement(trace_steps):
        signals.append(
            RiskSignal(
                "warn",
                "agent_disagreement",
                "Solver, tie-breaker, or verifier trace steps disagreed on the answer.",
            )
        )

    synthesizer_detail = _synthesizer_detail(trace_steps)
    if "tied=" in synthesizer_detail:
        signals.append(
            RiskSignal(
                "warn",
                "tournament_tie",
                "Tournament variants tied before tie-breaker/verifier adjudication.",
            )
        )
    elif _has_low_vote_margin(synthesizer_detail):
        signals.append(
            RiskSignal(
                "info",
                "low_vote_margin",
                "Tournament majority margin was only one vote.",
            )
        )

    ignored_markers = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.startswith("ignored_calculation_marker=")
        or diagnostic.startswith("ignored_negative_marker=")
    )
    if ignored_markers:
        signals.append(
            RiskSignal(
                "info",
                "broad_marker_ignored",
                "Classifier ignored broad marker(s): " + ",".join(ignored_markers),
            )
        )

    feature_set = set(features)
    if {"has_many_choices", "has_calculation"} <= feature_set:
        signals.append(
            RiskSignal(
                "info",
                "compound_many_choice_calculation",
                "Question combines many choices with calculation markers.",
            )
        )
    if {"has_many_choices", "has_negative"} <= feature_set:
        signals.append(
            RiskSignal(
                "info",
                "compound_negative_many_choice",
                "Question combines many choices with negative wording.",
            )
        )
    if {"has_long_context", "has_negative"} <= feature_set:
        signals.append(
            RiskSignal(
                "info",
                "compound_negative_long_context",
                "Question combines long context with negative wording.",
            )
        )

    confidence = _float_or_none(prediction.get("confidence"))
    if confidence is not None and confidence < quality_confidence_threshold:
        signals.append(
            RiskSignal(
                "info",
                "quality_low_confidence",
                f"Confidence {confidence:.4f} is below review target {quality_confidence_threshold:.2f}.",
            )
        )

    return tuple(signals)


def _classifier_detail(trace_steps: list[Any]) -> str:
    for step in trace_steps:
        if isinstance(step, dict) and step.get("role") == "classifier":
            return str(step.get("detail", ""))
    return ""


def _synthesizer_detail(trace_steps: list[Any]) -> str:
    for step in trace_steps:
        if isinstance(step, dict) and step.get("role") == "synthesizer":
            return str(step.get("detail", ""))
    return ""


def _parse_detail_list(detail: str, key: str) -> tuple[str, ...]:
    prefix = f"{key}="
    for part in detail.split(";"):
        stripped = part.strip()
        if stripped.startswith(prefix):
            values = [
                value.strip()
                for value in stripped[len(prefix) :].split(",")
                if value.strip()
            ]
            return tuple(dict.fromkeys(values))
    return ()


def _has_solver_disagreement(trace_steps: list[Any]) -> bool:
    answer_roles = {"solver", "tie-breaker", "verifier"}
    answers = {
        str(step.get("answer"))
        for step in trace_steps
        if isinstance(step, dict)
        and step.get("role") in answer_roles
        and step.get("answer")
    }
    return len(answers) > 1


def _has_low_vote_margin(detail: str) -> bool:
    counts = [
        int(match.group(2))
        for match in re.finditer(r"([A-Z]):(\d+)", detail)
    ]
    if len(counts) < 2:
        return False
    ordered = sorted(counts, reverse=True)
    return ordered[0] - ordered[1] <= 1


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
