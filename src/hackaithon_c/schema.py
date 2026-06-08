from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
QuestionKind = Literal[
    "reading",
    "calculation",
    "negative",
    "many_choice",
    "short",
    "general",
]


@dataclass(frozen=True)
class Problem:
    qid: str
    question: str
    choices: tuple[str, ...]

    @property
    def allowed_letters(self) -> str:
        return LETTERS[: len(self.choices)]


@dataclass(frozen=True)
class ProblemProfile:
    kind: QuestionKind
    reasons: tuple[str, ...]
    prompt_variant: str
    should_verify: bool
    should_tournament: bool


@dataclass(frozen=True)
class Prediction:
    qid: str
    answer: str
    model: str
    raw_answer: str
    strategy: str
    confidence: float
    question_kind: str = "general"
    prompt_variant: str = "direct"
    attempts: int = 1
    fallback_reason: str | None = None
