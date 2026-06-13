from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

from .schema import LETTERS, Problem
from .text import normalize_text


@dataclass(frozen=True)
class CalculationDecision:
    answer: str
    detail: str


@dataclass(frozen=True)
class CalculationRule:
    name: str
    label: str
    solve: Callable[[str], float | None]


@dataclass(frozen=True)
class CalculationDecisionRule:
    name: str
    label: str
    solve: Callable[[Problem, str], CalculationDecision | None]


def adjudicate_calculation(problem: Problem) -> CalculationDecision | None:
    """Deterministic checks for high-confidence textbook calculations."""
    normalized_question = normalize_text(problem.question)
    for rule in CALCULATION_DECISION_RULES:
        decision = rule.solve(problem, normalized_question)
        if decision is not None:
            return decision

    choice_values = _choice_numeric_values(problem.choices)
    if not choice_values:
        return None

    for rule in CALCULATION_RULES:
        result = rule.solve(normalized_question)
        if result is not None:
            return _nearest_choice(result, choice_values, rule.label)

    return None


def list_calculation_rules() -> tuple[CalculationRule, ...]:
    return CALCULATION_RULES


def list_calculation_decision_rules() -> tuple[CalculationDecisionRule, ...]:
    return CALCULATION_DECISION_RULES


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
    if not any(marker in text for marker in ("do cao", "chieu cao", "height")):
        return None
    if not any(marker in text for marker in ("toc do", "rate")):
        return None

    volume_rate = _number_after(
        text,
        (
            "toc do khong doi la",
            "toc do la",
            "toc do",
            "rate is",
            "rate of",
        ),
    )
    radius = _number_after(text, ("ban kinh", "radius"))
    if volume_rate is None or radius in (None, 0):
        return None
    return volume_rate / (math.pi * radius * radius)


def _solve_buffer_ph(text: str) -> float | None:
    if not any(marker in text for marker in ("dung dich dem", "buffer")):
        return None
    if not any(marker in text for marker in ("pka", "k_a")):
        return None
    if not any(marker in text for marker in ("nong do", "concentration")):
        return None

    pka = _number_after(text, ("k_a", "pka"))
    acid = _number_after_pattern(
        text,
        r"nong do cua [^.\d]{0,30}(?:\\text\{hb\}|hb)[^.\d]{0,20} la",
    )
    base = _number_after_pattern(
        text,
        r"nong do cua [^.\d]{0,30}(?:\\text\{b\}\^-|b-)[^.\d]{0,20} la",
    )
    if pka is None or acid in (None, 0) or base is None:
        return None
    return pka + math.log10(base / acid)


def _solve_carbon_percent_from_co2(text: str) -> float | None:
    if not any(marker in text for marker in ("co2", "carbon dioxide")):
        return None
    if not any(marker in text for marker in ("cacbon", "carbon")):
        return None
    if not any(marker in text for marker in ("phan tram", "percent", "%")):
        return None

    sample: float | None = None
    sample_match = re.search(
        r"(?:dot\s*)?(-?\d+(?:[\.,]\d+)?)\s*g[^.]{0,60}(?:mau|sample|thep|steel)",
        text,
    )
    co2_match = re.search(
        r"(?:thu duoc|produced|obtained)[^\d]{0,30}(-?\d+(?:[\.,]\d+)?)\s*g[^.]{0,30}(?:co2|carbon dioxide)",
        text,
    )
    if sample_match is not None:
        sample = _parse_number(sample_match.group(1))
    if sample in (None, 0) or co2_match is None:
        return None
    co2_mass = _parse_number(co2_match.group(1))
    carbon_mass = co2_mass * 12 / 44
    return carbon_mass / sample * 100


def _solve_wire_length_from_power_current_resistivity(text: str) -> float | None:
    if not any(marker in text for marker in ("cong suat", "power")):
        return None
    if not any(marker in text for marker in ("cuong do dong dien", "current")):
        return None
    if not any(marker in text for marker in ("dien tro suat", "resistivity", "ρ", "rho")):
        return None
    if not any(marker in text for marker in ("tiet dien", "cross section", "section", "s =")):
        return None
    if not any(marker in text for marker in ("chieu dai", "length")):
        return None

    power_match = re.search(r"(-?\d+(?:[\.,]\d+)?)\s*w\b", text)
    current_match = re.search(r"(-?\d+(?:[\.,]\d+)?)\s*a\b", text)
    rho_match = re.search(
        r"(?:dien tro suat|resistivity|ρ|rho)[^=0-9]{0,30}=?\s*"
        r"(-?\d+(?:[\.,]\d+)?)\s*\.?\s*10\s*[−–-]\s*(\d+)",
        text,
    )
    area_match = re.search(
        r"(?:tiet dien|cross section|section|s)[^=0-9]{0,30}=?\s*"
        r"(-?\d+(?:[\.,]\d+)?)\s*mm",
        text,
    )
    if (
        power_match is None
        or current_match is None
        or rho_match is None
        or area_match is None
    ):
        return None
    power = _parse_number(power_match.group(1))
    current = _parse_number(current_match.group(1))
    rho = _parse_number(rho_match.group(1)) * 10 ** (-int(rho_match.group(2)))
    area = _parse_number(area_match.group(1)) * 1e-6
    if current == 0 or rho == 0:
        return None
    resistance = power / (current * current)
    return resistance * area / rho


def _solve_ideal_transformer_primary_current(text: str) -> float | None:
    if not any(marker in text for marker in ("bien ap", "transformer")):
        return None
    if not any(marker in text for marker in ("ly tuong", "ideal")):
        return None
    if not any(marker in text for marker in ("so cap", "primary")):
        return None
    if not any(marker in text for marker in ("thu cap", "secondary")):
        return None
    if not any(marker in text for marker in ("dong dien", "current")):
        return None

    primary_turns_match = re.search(
        r"(?:so cap|primary)[^.]{0,80}?(-?\d+(?:[\.,]\d+)?)\s*(?:vong|turn)",
        text,
    )
    secondary_turns_match = re.search(
        r"(?:thu cap|secondary)[^.]{0,80}?(-?\d+(?:[\.,]\d+)?)\s*(?:vong|turn)",
        text,
    )
    secondary_current_match = re.search(
        r"(?:dong dien thu cap|secondary current)[^.]{0,80}?(-?\d+(?:[\.,]\d+)?)\s*a\b",
        text,
    )
    if (
        primary_turns_match is None
        or secondary_turns_match is None
        or secondary_current_match is None
    ):
        return None
    primary_turns = _parse_number(primary_turns_match.group(1))
    secondary_turns = _parse_number(secondary_turns_match.group(1))
    secondary_current = _parse_number(secondary_current_match.group(1))
    if primary_turns == 0:
        return None
    return secondary_current * secondary_turns / primary_turns


def _solve_quadratic_production_max_labor(text: str) -> float | None:
    if not any(marker in text for marker in ("ham san xuat", "production function")):
        return None
    if not any(marker in text for marker in ("toi da hoa san luong", "maximize output")):
        return None
    match = re.search(
        r"q\s*=\s*(-?\d+(?:[\.,]\d+)?)\s*l\s*[-−–]\s*(\d+(?:[\.,]\d+)?)\s*l\^?2",
        text,
    )
    if match is None:
        return None
    linear = _parse_number(match.group(1))
    quadratic = _parse_number(match.group(2))
    if quadratic == 0:
        return None
    return linear / (2 * quadratic)


# Removed (2026-06-13): the depreciable-asset-sale decision rule used a hard-coded asset-life
# lookup (e.g. "printing press" -> 5.0 years) keyed off a specific public-463 item, which is a
# public-test hard-code. General quantitative recovery is handled by the TIR/router path.
CALCULATION_DECISION_RULES: tuple[CalculationDecisionRule, ...] = ()


CALCULATION_RULES: tuple[CalculationRule, ...] = (
    CalculationRule("gdp_inflation", "gdp inflation", _solve_gdp_inflation),
    CalculationRule(
        "cylinder_fill_rate",
        "cylinder fill rate",
        _solve_cylinder_fill_rate,
    ),
    CalculationRule("buffer_ph", "buffer pH", _solve_buffer_ph),
    CalculationRule(
        "carbon_percent_from_co2",
        "carbon percent from CO2",
        _solve_carbon_percent_from_co2,
    ),
    CalculationRule(
        "wire_length_from_power_current_resistivity",
        "wire length from power, current, and resistivity",
        _solve_wire_length_from_power_current_resistivity,
    ),
    CalculationRule(
        "ideal_transformer_primary_current",
        "ideal transformer primary current",
        _solve_ideal_transformer_primary_current,
    ),
    CalculationRule(
        "quadratic_production_max_labor",
        "quadratic production maximum labor",
        _solve_quadratic_production_max_labor,
    ),
)


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
        value = _parse_choice_value(choice)
        if value is not None:
            values.append((LETTERS[index], value))
    return tuple(values)


def _choice_numeric_pairs(choices: tuple[str, ...]) -> tuple[tuple[str, float, float], ...]:
    values: list[tuple[str, float, float]] = []
    for index, choice in enumerate(choices):
        matches = re.findall(r"-?\d+(?:[\.,]\d+)?", choice)
        if len(matches) >= 2:
            values.append(
                (
                    LETTERS[index],
                    _parse_number(matches[0]),
                    _parse_number(matches[1]),
                )
            )
    return tuple(values)


def _parse_choice_value(choice: str) -> float | None:
    compact = choice.lower().replace(" ", "").replace("$", "")
    pi_fraction_patterns = (
        r"\\frac\{(-?\d+(?:[\.,]\d+)?)\}\{(-?\d+(?:[\.,]\d+)?)?(?:\\pi|π|pi)\}",
        r"(-?\d+(?:[\.,]\d+)?)/(?:\(?(-?\d+(?:[\.,]\d+)?)?(?:\\pi|π|pi)\)?)",
    )
    for pattern in pi_fraction_patterns:
        match = re.search(pattern, compact)
        if not match:
            continue
        numerator = _parse_number(match.group(1))
        denominator = _parse_number(match.group(2)) if match.group(2) else 1.0
        if denominator == 0:
            return None
        return numerator / (denominator * math.pi)

    match = re.search(r"-?\d+(?:[\.,]\d+)?", choice)
    if not match:
        return None
    return _parse_number(match.group(0))


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


def _number_after_pattern(text: str, pattern: str) -> float | None:
    match = re.search(pattern + r"[^-\d]{0,20}(-?\d+(?:[\.,]\d+)?)", text)
    if not match:
        return None
    return _parse_number(match.group(1))


def _years_after_sale(text: str) -> float | None:
    match = re.search(r"sau\s+(-?\d+(?:[\.,]\d+)?)\s+nam", text)
    if match:
        return _parse_number(match.group(1))
    word_years = {
        "mot": 1.0,
        "hai": 2.0,
        "ba": 3.0,
        "bon": 4.0,
        "nam": 5.0,
        "sau": 6.0,
        "bay": 7.0,
        "tam": 8.0,
        "chin": 9.0,
        "muoi": 10.0,
    }
    match = re.search(r"sau\s+([a-z]+)\s+nam", text)
    if match:
        return word_years.get(match.group(1))
    match = re.search(r"after\s+(-?\d+(?:[\.,]\d+)?)\s+years?", text)
    if match:
        return _parse_number(match.group(1))
    return None


def _parse_number(raw: str) -> float:
    if "," in raw and "." in raw:
        decimal_separator = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        cleaned = raw.replace(thousands_separator, "")
        return float(cleaned.replace(decimal_separator, "."))
    if "." in raw:
        head, tail = raw.rsplit(".", 1)
        if len(tail) == 3 and head.replace("-", "").isdigit():
            return float(head.replace(".", "") + tail)
        return float(raw)
    if "," in raw:
        head, tail = raw.rsplit(",", 1)
        if len(tail) == 3 and head.replace("-", "").isdigit():
            return float(head.replace(",", "") + tail)
        return float(raw.replace(",", "."))
    return float(raw)
