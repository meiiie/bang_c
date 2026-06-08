from __future__ import annotations

import re

from .schema import Problem


def normalize_answer(raw_answer: str, problem: Problem) -> str | None:
    text = raw_answer.strip().upper()
    allowed = set(problem.allowed_letters)
    if text in allowed:
        return text

    for marker in ("ANSWER", "FINAL", "RESULT", "DAP AN", "KET QUA"):
        pattern = rf"\b{marker}\b\s*[:=\-]?\s*([A-Z])\b"
        matches = re.findall(pattern, text)
        for candidate in reversed(matches):
            if candidate in allowed:
                return candidate

    line_candidates: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        match = re.fullmatch(r"(?:OPTION\s+)?([A-Z])[\).:]?", cleaned)
        if match:
            line_candidates.append(match.group(1))
    for candidate in reversed(line_candidates):
        if candidate in allowed:
            return candidate

    if len(text) <= 8:
        candidates = re.findall(r"\b([A-Z])\b", text)
        for candidate in reversed(candidates):
            if candidate in allowed:
                return candidate
    return None
