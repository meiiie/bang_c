from __future__ import annotations

import re
import unicodedata

from .schema import Problem


_STOPWORDS = {
    "la",
    "cua",
    "va",
    "hoac",
    "trong",
    "theo",
    "duoc",
    "cac",
    "cho",
    "voi",
    "mot",
    "nhung",
    "noi",
    "dung",
    "cau",
    "hoi",
}


def fallback_answer(problem: Problem) -> tuple[str, float, str]:
    scores = [_score_choice(problem.question, choice) for choice in problem.choices]
    if not scores:
        return "A", 0.0, "fallback_empty"
    best = max(range(len(scores)), key=lambda index: scores[index])
    confidence = 0.05
    if sum(scores) > 0:
        confidence = min(0.45, scores[best] / max(1.0, sum(scores)))
    return problem.allowed_letters[best], confidence, "fallback_overlap"


def _score_choice(question: str, choice: str) -> float:
    haystack = _normalize(question)
    terms = [term for term in _tokens(choice) if term not in _STOPWORDS and len(term) > 2]
    if not terms:
        return 0.0
    score = 0.0
    for term in terms:
        count = haystack.count(term)
        if count:
            score += min(3, count)
    phrase = _normalize(choice)
    if phrase and phrase in haystack:
        score += 5.0
    return score


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize(text))


def _normalize(text: str) -> str:
    without_marks = "".join(
        char
        for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks)
