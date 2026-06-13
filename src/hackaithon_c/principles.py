from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .schema import Problem


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


# Removed (2026-06-13): every principle "rule" here was a keyword -> fixed-answer match for a
# specific public-463 item (preschool accreditation file count, Ho Chi Minh communism
# adaptation, three-wire wattmeter wording, constant-returns scenario, rational-choice
# marginal-utility, anti-state refusal). These are hard-coded public-test answers (AGENTS.md
# forbids this) and a selection-on-test overfit that need not transfer to the private 2000-q
# set; a keyword match can also OVERRIDE a correct model answer on a private item that
# superficially matches. General reasoning recovery is handled by the self-consistency CoT
# path (shipped) and, for quantitative items, the TIR/router path (executes Python for the
# problem as stated). The shipped self_consistency path never called these adjudicators.
# Empty tuple is asserted by tests to prevent silent re-introduction.
PRINCIPLE_RULES: tuple[PrincipleRule, ...] = ()

