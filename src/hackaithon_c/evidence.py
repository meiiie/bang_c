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
