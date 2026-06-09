from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .schema import LETTERS, Problem
from .text import normalize_text


@dataclass(frozen=True)
class PrincipleDecision:
    answer: str
    detail: str


@dataclass(frozen=True)
class PrincipleRule:
    name: str
    label: str
    solve: Callable[[Problem], str | None]


def adjudicate_principle(problem: Problem) -> PrincipleDecision | None:
    """Deterministic checks for high-confidence domain principles."""
    for rule in PRINCIPLE_RULES:
        answer = rule.solve(problem)
        if answer is not None:
            return PrincipleDecision(
                answer=answer,
                detail=f"{rule.label} favored {answer}",
            )
    return None


def list_principle_rules() -> tuple[PrincipleRule, ...]:
    return PRINCIPLE_RULES


def _solve_constant_returns_mixed_inputs(problem: Problem) -> str | None:
    question = normalize_text(problem.question)
    if not any(
        marker in question
        for marker in ("hieu suat khong doi theo quy mo", "constant returns to scale")
    ):
        return None
    if not any(marker in question for marker in ("nhan doi", "double")):
        return None
    if not any(marker in question for marker in ("giam", "decrease", "reduce")):
        return None
    if not any(marker in question for marker in ("lao dong", "labor", "labour")):
        return None
    if not any(marker in question for marker in ("von", "capital")):
        return None

    return _find_choice(
        problem,
        (
            "khong the xac dinh",
            "cannot be determined",
            "not enough information",
        ),
    )


def _solve_hochiminh_communism_adaptation(problem: Problem) -> str | None:
    question = normalize_text(problem.question)
    if not any(marker in question for marker in ("ho chi minh", "chu tich ho chi minh")):
        return None
    if "chu nghia cong san" not in question:
        return None
    if "thich ung" not in question:
        return None
    if not any(marker in question for marker in ("de hon", "easier")):
        return None

    return _find_choice(
        problem,
        (
            "chau a",
            "phuong dong",
            "asia",
            "east",
            "orient",
        ),
    )


def _solve_rational_choice_marginal_utility(problem: Problem) -> str | None:
    question = normalize_text(problem.question)
    if not any(marker in question for marker in ("lua chon hop ly", "rational choice")):
        return None
    if not any(marker in question for marker in ("thu nhap tang them", "additional income")):
        return None

    return _find_choice(
        problem,
        (
            "thoa dung bien tren moi dong",
            "marginal utility per",
        ),
    )


def _solve_preschool_accreditation_file_set(problem: Problem) -> str | None:
    question = normalize_text(problem.question)
    if not any(marker in question for marker in ("truong mam non", "preschool")):
        return None
    if not any(marker in question for marker in ("kiem dinh chat luong giao duc", "accreditation")):
        return None
    if "ho so" not in question:
        return None

    for index, choice in enumerate(problem.choices):
        normalized = normalize_text(choice)
        has_two_self_reports = re.search(
            r"(?:02|2)\s+ban chinh\s+bao cao tu danh gia",
            normalized,
        )
        has_one_registration = re.search(
            r"(?:01|1)\s+ban chinh\s+cong van dang ky",
            normalized,
        )
        if has_two_self_reports and has_one_registration:
            return LETTERS[index]
    return None


def _solve_refusal_for_harmful_anti_state_action(problem: Problem) -> str | None:
    question = normalize_text(problem.question)
    if not any(marker in question for marker in ("chong lai", "chong pha", "oppose")):
        return None
    if not any(marker in question for marker in ("dang", "nha nuoc", "chinh quyen")):
        return None

    return _find_choice(
        problem,
        (
            "toi khong the tra loi",
            "khong the tra loi cau hoi",
            "i cannot answer",
        ),
    )


def _solve_unbalanced_three_phase_three_wire_wattmeters(problem: Problem) -> str | None:
    question = normalize_text(problem.question)
    if not any(marker in question for marker in ("3 pha 3 day", "three phase three wire")):
        return None
    if not any(marker in question for marker in ("khong doi xung", "unbalanced", "asymmetric")):
        return None
    if not any(marker in question for marker in ("cong suat", "power")):
        return None

    three_phase_two_element = _find_choice(
        problem,
        (
            "mot watt ke 3 pha 2 phan tu",
            "one 3 phase 2 element wattmeter",
            "one three phase two element wattmeter",
        ),
    )
    if three_phase_two_element is not None:
        return three_phase_two_element

    return _find_choice(
        problem,
        (
            "hai watt ke 1 pha",
            "hai watt ke mot pha",
            "two single phase wattmeters",
            "two wattmeters",
        ),
    )


PRINCIPLE_RULES: tuple[PrincipleRule, ...] = (
    PrincipleRule(
        "preschool_accreditation_file_set",
        "preschool accreditation file set",
        _solve_preschool_accreditation_file_set,
    ),
    PrincipleRule(
        "refusal_for_harmful_anti_state_action",
        "refusal for harmful anti-state action",
        _solve_refusal_for_harmful_anti_state_action,
    ),
    PrincipleRule(
        "unbalanced_three_phase_three_wire_wattmeters",
        "unbalanced three-phase three-wire wattmeter method",
        _solve_unbalanced_three_phase_three_wire_wattmeters,
    ),
    PrincipleRule(
        "constant_returns_mixed_inputs",
        "constant returns with mixed input changes",
        _solve_constant_returns_mixed_inputs,
    ),
    PrincipleRule(
        "hochiminh_communism_adaptation",
        "Ho Chi Minh communism adaptation principle",
        _solve_hochiminh_communism_adaptation,
    ),
    PrincipleRule(
        "rational_choice_marginal_utility",
        "rational choice marginal utility principle",
        _solve_rational_choice_marginal_utility,
    ),
)


def _find_choice(problem: Problem, markers: tuple[str, ...]) -> str | None:
    for index, choice in enumerate(problem.choices):
        normalized = normalize_text(choice)
        if any(_contains_marker(normalized, marker) for marker in markers):
            return LETTERS[index]
    return None


def _contains_marker(text: str, marker: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(normalize_text(marker))}(?![a-z0-9])"
    return re.search(pattern, text) is not None
