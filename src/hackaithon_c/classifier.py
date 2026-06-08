from __future__ import annotations

import re

from .schema import Problem, ProblemProfile


_CALCULATION_TERMS = (
    "tinh",
    "tinh toan",
    "phan tram",
    "ty le",
    "do co gian",
    "bao nhieu",
    "gia tri",
    "cong thuc",
    "x =",
    "so luong",
)
_NEGATIVE_TERMS = (
    "khong dung",
    "khong phai",
    "ngoai tru",
    "sai",
    "it phu hop",
    "khong duoc",
)
_READING_TERMS = (
    "doan thong tin",
    "noi dung",
    "theo noi dung",
    "duoc cung cap",
    "trong doan",
    "title:",
    "tieu de",
)


def classify_problem(problem: Problem) -> ProblemProfile:
    text = _normalize(problem.question)
    focus = _normalize(_question_focus(problem.question))
    reasons: list[str] = []

    if len(problem.choices) > 4:
        reasons.append("many_choices")
        return ProblemProfile(
            kind="many_choice",
            reasons=tuple(reasons),
            prompt_variant="elimination",
            should_verify=True,
            should_tournament=True,
        )

    if any(term in focus for term in _CALCULATION_TERMS):
        reasons.append("calculation_terms")
        return ProblemProfile(
            kind="calculation",
            reasons=tuple(reasons),
            prompt_variant="calculation",
            should_verify=True,
            should_tournament=False,
        )

    if any(term in focus for term in _NEGATIVE_TERMS):
        reasons.append("negative_terms")
        return ProblemProfile(
            kind="negative",
            reasons=tuple(reasons),
            prompt_variant="elimination",
            should_verify=True,
            should_tournament=True,
        )

    if len(problem.question) > 1800 or any(term in text for term in _READING_TERMS):
        reasons.append("reading_context")
        return ProblemProfile(
            kind="reading",
            reasons=tuple(reasons),
            prompt_variant="evidence",
            should_verify=True,
            should_tournament=False,
        )

    if len(problem.question) < 280:
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


def _question_focus(question: str) -> str:
    markers = (
        r"\n\s*Cau hoi\s*:",
        r"\n\s*Câu hỏi\s*:",
        r"\n\s*Question\s*:",
    )
    for marker in markers:
        match = re.search(marker, question, flags=re.IGNORECASE)
        if match:
            return question[match.end() :].strip()
    return question[-900:]


def _normalize(text: str) -> str:
    import unicodedata

    without_marks = "".join(
        char
        for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks)
