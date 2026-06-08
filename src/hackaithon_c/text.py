from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    without_marks = "".join(
        char
        for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_marks).strip()


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    normalized_markers = tuple(normalize_text(marker) for marker in markers)
    return any(marker and marker in normalized for marker in normalized_markers)


def focus_text(question: str, question_markers: tuple[str, ...], tail_chars: int) -> str:
    normalized = normalize_text(question)
    normalized_markers = tuple(normalize_text(marker) for marker in question_markers)
    best_position = -1
    best_marker = ""
    for marker in normalized_markers:
        position = normalized.rfind(marker)
        if position > best_position:
            best_position = position
            best_marker = marker
    if best_position >= 0:
        return normalized[best_position + len(best_marker) :].strip()
    return normalized[-tail_chars:]
