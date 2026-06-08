from __future__ import annotations

from dataclasses import dataclass


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class Problem:
    qid: str
    question: str
    choices: tuple[str, ...]

    @property
    def allowed_letters(self) -> str:
        return LETTERS[: len(self.choices)]


@dataclass(frozen=True)
class Prediction:
    qid: str
    answer: str
    model: str
    raw_answer: str
    strategy: str
    confidence: float
