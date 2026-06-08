from __future__ import annotations

import re

from .schema import Problem


def normalize_answer(raw_answer: str, problem: Problem) -> str | None:
    text = raw_answer.strip().upper()
    allowed = set(problem.allowed_letters)
    if text in allowed:
        return text

    # Gemma 4 can emit empty thought tags before the final answer. Prefer the
    # last visible letter because final answers usually come after those tags.
    candidates = re.findall(r"\b([A-Z])\b", text)
    for candidate in reversed(candidates):
        if candidate in allowed:
            return candidate

    # Some models answer "Đáp án: A" without clean word boundaries.
    for marker in ("ĐÁP ÁN", "ANSWER", "FINAL", "KẾT QUẢ"):
        position = text.rfind(marker)
        if position >= 0:
            tail = text[position:]
            for char in tail:
                if char in allowed:
                    return char
    return None
