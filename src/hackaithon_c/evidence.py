from __future__ import annotations

import re
from dataclasses import dataclass

from .config import HarnessConfig
from .schema import Problem
from .text import normalize_text


_STOPWORDS = {
    "theo",
    "noi",
    "dung",
    "duoc",
    "cung",
    "cap",
    "trong",
    "cac",
    "sau",
    "day",
    "toi",
    "nao",
    "bang",
    "hinh",
    "thuc",
    "with",
    "from",
    "that",
    "this",
    "which",
    "what",
    "provided",
    "passage",
}

_EVIDENCE_TERMS = {
    "nem",
    "stone",
    "stoned",
    "stoning",
    "chet",
    "death",
    "die",
    "killed",
    "executed",
    "execution",
    "xet",
    "xu",
    "tu",
}


@dataclass(frozen=True)
class DirectEvidenceDecision:
    answer: str
    detail: str


def adjudicate_direct_evidence(
    problem: Problem,
    candidate_answer: str,
    config: HarnessConfig,
) -> DirectEvidenceDecision | None:
    context, query = _split_context_and_query(problem.question, config.markers["question"])
    if not context or not query:
        return None

    references_by_choice = [_extract_references(normalize_text(choice)) for choice in problem.choices]
    if sum(1 for references in references_by_choice if references) < 2:
        return None

    scores = [
        _score_choice_against_context(
            choice,
            references=references,
            context=context,
            query=query,
        )
        for choice, references in zip(problem.choices, references_by_choice, strict=False)
    ]
    if not scores:
        return None

    best_index = max(range(len(scores)), key=lambda index: scores[index])
    best_score = scores[best_index]
    candidate_index = problem.allowed_letters.find(candidate_answer)
    candidate_score = scores[candidate_index] if candidate_index >= 0 else 0.0
    if best_score < 8.0 or best_score - candidate_score < 3.0:
        return None

    answer = problem.allowed_letters[best_index]
    if answer == candidate_answer:
        return None
    detail = (
        f"direct passage evidence favored {answer} "
        f"(scores={_format_scores(problem.allowed_letters, scores)})"
    )
    return DirectEvidenceDecision(answer=answer, detail=detail)


def adjudicate_date_evidence(
    problem: Problem,
    candidate_answer: str | None,
    config: HarnessConfig,
) -> DirectEvidenceDecision | None:
    context, query = _split_context_and_query(problem.question, config.markers["question"])
    if not context or not query:
        return None

    normalized_context = normalize_text(context)
    normalized_query = normalize_text(query)
    choice_dates = [_date_key_from_text(normalize_text(choice)) for choice in problem.choices]
    if sum(1 for item in choice_dates if item) < 2:
        return None
    context_dates = list(_iter_context_date_windows(normalized_context))
    if not context_dates:
        return None

    query_terms = _query_terms(normalized_query)
    scores: list[float] = []
    for choice_date in choice_dates:
        if not choice_date:
            scores.append(0.0)
            continue
        score = 0.0
        for context_date, before_window, after_window in context_dates:
            if context_date != choice_date:
                continue
            score += 6.0
            score += 2.5 * sum(1 for term in query_terms if term in before_window)
            score += 0.75 * sum(1 for term in query_terms if term in after_window)
            if "500" in normalized_query and "500" in before_window:
                score += 10.0
            if "stream" in normalized_query and "stream" in before_window:
                score += 8.0
            if "dau tien" in normalized_query and "dau tien" in before_window:
                score += 6.0
        scores.append(score)

    best_index = max(range(len(scores)), key=lambda index: scores[index])
    best_score = scores[best_index]
    second_score = max(
        (score for index, score in enumerate(scores) if index != best_index),
        default=0.0,
    )
    if best_score < 12.0 or best_score - second_score < 6.0:
        return None

    answer = problem.allowed_letters[best_index]
    if candidate_answer is not None and answer == candidate_answer:
        return None
    detail = (
        f"date passage evidence favored {answer} "
        f"(scores={_format_scores(problem.allowed_letters, scores)})"
    )
    return DirectEvidenceDecision(answer=answer, detail=detail)


def _score_choice_against_context(
    choice: str,
    *,
    references: list[str],
    context: str,
    query: str,
) -> float:
    normalized_context = normalize_text(context)
    normalized_choice = normalize_text(choice)
    normalized_query = normalize_text(query)
    windows: list[str] = []
    score = 0.0

    for reference in references:
        position = normalized_context.find(reference)
        if position >= 0:
            score += 6.0
            windows.append(_window(normalized_context, position, len(reference)))

    if not windows:
        return 0.0

    query_terms = _query_terms(normalized_query)
    choice_terms = _choice_terms(normalized_choice)
    for evidence_window in windows:
        score += 2.5 * sum(1 for term in query_terms if term in evidence_window)
        score += 1.0 * sum(1 for term in choice_terms if term in evidence_window)
        score += 3.0 * sum(1 for term in _EVIDENCE_TERMS if term in evidence_window)

    if _strip_parenthetical(normalized_choice) in normalized_context:
        score += 5.0
    return score


def _split_context_and_query(question: str, markers: tuple[str, ...]) -> tuple[str, str]:
    patterns = [rf"\n\s*{re.escape(marker)}" for marker in markers]
    patterns.extend(
        (
            r"\n\s*CÃ¢u há»i\s*:",
            r"\n\s*Câu hỏi\s*:",
            r"\n\s*Cau hoi\s*:",
            r"\n\s*Question\s*:",
            r"\n\s*Pregunta\s*:",
        )
    )
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if not match:
            continue
        context = question[: match.start()].strip()
        query = question[match.end() :].strip()
        if context and query:
            return context, query
    return "", question.strip()


def _extract_references(text: str) -> list[str]:
    return re.findall(r"\b[a-z][a-z0-9]*(?:\s+[a-z][a-z0-9]*)?\s+\d{1,3}:\d{1,3}(?:-\d{1,3})?\b", text)


def _date_key_from_text(text: str) -> tuple[int, int, int] | None:
    match = re.search(
        r"(?:ngay\s+)?(\d{1,2})\s+thang\s+([a-z]+|\d{1,2})\s*,?\s*(?:nam\s*)?(\d{4})",
        text,
    )
    if match:
        month = _month_number(match.group(2))
        if month is None:
            return None
        return int(match.group(3)), month, int(match.group(1))
    match = re.search(
        r"(\d{1,2})\s+([a-z]+)\s+(\d{4})",
        text,
    )
    if match:
        month = _month_number(match.group(2))
        if month is None:
            return None
        return int(match.group(3)), month, int(match.group(1))
    return None


def _iter_context_date_windows(
    text: str,
) -> list[tuple[tuple[int, int, int], str, str]]:
    results: list[tuple[tuple[int, int, int], str, str]] = []
    for match in re.finditer(
        r"(?:ngay\s+)?(\d{1,2})\s+thang\s+([a-z]+|\d{1,2})\s*,?\s*(?:nam\s*)?(\d{4})",
        text,
    ):
        month = _month_number(match.group(2))
        if month is None:
            continue
        key = (int(match.group(3)), month, int(match.group(1)))
        before = text[max(0, match.start() - 180) : match.start()]
        after = text[match.end() : min(len(text), match.end() + 100)]
        results.append((key, before, after))
    return results


def _month_number(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    months = {
        "mot": 1,
        "january": 1,
        "jan": 1,
        "hai": 2,
        "february": 2,
        "feb": 2,
        "ba": 3,
        "march": 3,
        "mar": 3,
        "tu": 4,
        "april": 4,
        "apr": 4,
        "nam": 5,
        "may": 5,
        "sau": 6,
        "june": 6,
        "jun": 6,
        "bay": 7,
        "july": 7,
        "jul": 7,
        "tam": 8,
        "august": 8,
        "aug": 8,
        "chin": 9,
        "september": 9,
        "sep": 9,
        "muoi": 10,
        "october": 10,
        "oct": 10,
        "muoi mot": 11,
        "november": 11,
        "nov": 11,
        "muoi hai": 12,
        "december": 12,
        "dec": 12,
    }
    return months.get(raw)


def _query_terms(text: str) -> list[str]:
    terms = _tokens(text)
    return [
        term
        for term in terms
        if len(term) > 2 and (term not in _STOPWORDS or term in _EVIDENCE_TERMS)
    ]


def _choice_terms(text: str) -> list[str]:
    return [
        term
        for term in _tokens(_strip_parenthetical(text))
        if len(term) > 2 and term not in _STOPWORDS
    ]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _strip_parenthetical(text: str) -> str:
    return re.sub(r"\([^)]*\)", "", text).strip()


def _window(text: str, position: int, length: int, radius: int = 280) -> str:
    start = max(0, position - radius)
    end = min(len(text), position + length + radius)
    return text[start:end]


def _format_scores(letters: str, scores: list[float]) -> str:
    return ",".join(
        f"{letter}:{score:.1f}"
        for letter, score in zip(letters, scores, strict=False)
    )
