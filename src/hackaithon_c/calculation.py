from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .schema import LETTERS, Problem
from .text import normalize_text


@dataclass(frozen=True)
class CalculationDecision:
    answer: str
    detail: str


def adjudicate_calculation(problem: Problem) -> CalculationDecision | None:
    """Deterministic checks for high-confidence textbook calculations."""
    normalized_question = normalize_text(problem.question)
    choice_values = _choice_numeric_values(problem.choices)
    if not choice_values:
        return None

    result = _solve_gdp_inflation(normalized_question)
    if result is not None:
        return _nearest_choice(result, choice_values, "gdp inflation")

    result = _solve_cylinder_fill_rate(normalized_question)
    if result is not None:
        return _nearest_choice(result, choice_values, "cylinder fill rate")

    return None


def _solve_gdp_inflation(text: str) -> float | None:
    if "gdp" not in text:
        return None
    if not any(marker in text for marker in ("danh nghia", "nominal")):
        return None
    if not any(marker in text for marker in ("thuc te", "real")):
        return None
    if not any(marker in text for marker in ("chi so gia", "deflator", "price index")):
        return None

    nominal = _number_after(text, ("gdp danh nghia", "nominal gdp"))
    real = _number_after(text, ("gdp thuc te", "real gdp"))
    previous = _number_after(
        text,
        ("nam truoc", "previous year", "last year", "previous"),
    )
    if nominal is None or real is None or previous in (None, 0):
        return None
    current_deflator = nominal / real * 100
    return (current_deflator - previous) / previous * 100


def _solve_cylinder_fill_rate(text: str) -> float | None:
    if not any(marker in text for marker in ("hinh tru", "cylinder")):
        return None
    if not any(marker in text for marker in ("ban kinh", "radius")):
        return None
    if not any(marker in text for marker in ("do cao", "height")):
        return None
    if not any(marker in text for marker in ("toc do", "rate")):
        return None

    volume_rate = _number_after(
        text,
        (
            "toc do khong doi la",
            "toc do la",
            "rate is",
            "rate of",
        ),
    )
    radius = _number_after(text, ("ban kinh", "radius"))
    if volume_rate is None or radius in (None, 0):
        return None
    return volume_rate / (math.pi * radius * radius)


def _nearest_choice(
    value: float,
    choice_values: tuple[tuple[str, float], ...],
    label: str,
) -> CalculationDecision | None:
    best_letter, best_value = min(
        choice_values,
        key=lambda item: abs(item[1] - value),
    )
    gap = abs(best_value - value)
    second_gap = min(
        (
            abs(candidate - value)
            for letter, candidate in choice_values
            if letter != best_letter
        ),
        default=float("inf"),
    )
    tolerance = max(0.05, abs(value) * 0.08)
    if gap > tolerance and second_gap < float("inf"):
        return None
    if second_gap <= gap * 1.25:
        return None
    return CalculationDecision(
        answer=best_letter,
        detail=(
            f"{label} calculation favored {best_letter} "
            f"(value={value:.4g}, choice={best_value:.4g})"
        ),
    )


def _choice_numeric_values(choices: tuple[str, ...]) -> tuple[tuple[str, float], ...]:
    values: list[tuple[str, float]] = []
    for index, choice in enumerate(choices):
        match = re.search(r"-?\d+(?:[\.,]\d+)?", choice)
        if match:
            values.append((LETTERS[index], _parse_number(match.group(0))))
    return tuple(values)


def _number_after(text: str, markers: tuple[str, ...]) -> float | None:
    for marker in markers:
        position = text.find(marker)
        if position < 0:
            continue
        segment = text[position + len(marker) : position + len(marker) + 140]
        match = re.search(r"-?\d+(?:[\.,]\d+)?", segment)
        if match:
            return _parse_number(match.group(0))
    return None


def _parse_number(raw: str) -> float:
    return float(raw.replace(",", "."))
