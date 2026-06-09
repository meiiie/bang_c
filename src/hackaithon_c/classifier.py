from __future__ import annotations

from .config import HarnessConfig
from .schema import Problem, ProblemProfile
from .text import contains_any, focus_text, normalize_text


def classify_problem(problem: Problem, config: HarnessConfig) -> ProblemProfile:
    thresholds = config.thresholds
    markers = config.markers
    full_text = normalize_text(problem.question)
    focus = focus_text(
        problem.question,
        markers["question"],
        thresholds["focus_tail_chars"],
    )
    reasons: list[str] = []

    if len(problem.choices) >= thresholds["many_choice_min"]:
        reasons.append("many_choices")
        return ProblemProfile(
            kind="many_choice",
            reasons=tuple(reasons),
            prompt_variant="elimination",
            should_verify=True,
            should_tournament=True,
        )

    if contains_any(focus, markers["calculation"]):
        reasons.append("calculation_markers")
        return ProblemProfile(
            kind="calculation",
            reasons=tuple(reasons),
            prompt_variant="calculation",
            should_verify=True,
            should_tournament=True,
        )

    if contains_any(focus, markers["negative"]):
        reasons.append("negative_markers")
        return ProblemProfile(
            kind="negative",
            reasons=tuple(reasons),
            prompt_variant="elimination",
            should_verify=True,
            should_tournament=True,
        )

    if len(problem.question) > thresholds["long_context_chars"] or contains_any(
        full_text,
        markers["context"],
    ):
        reasons.append("context_markers_or_long_text")
        return ProblemProfile(
            kind="reading",
            reasons=tuple(reasons),
            prompt_variant="evidence",
            should_verify=True,
            should_tournament=False,
        )

    if len(problem.question) < thresholds["short_question_chars"]:
        reasons.append("short_question")
        return ProblemProfile(
            kind="short",
            reasons=tuple(reasons),
            prompt_variant="direct",
            should_verify=False,
            should_tournament=False,
        )

    reasons.append("general_default")
    return ProblemProfile(
        kind="general",
        reasons=tuple(reasons),
        prompt_variant="direct",
        should_verify=True,
        should_tournament=False,
    )
