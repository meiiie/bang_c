from __future__ import annotations

import re

from .config import HarnessConfig
from .schema import Problem, ProblemProfile
from .text import focus_text, normalize_text


# Topic / ambiguous markers that name a quantity or concept but do NOT by themselves
# imply a computation (e.g. "công thức"/"formula", "giá trị"/"value"). They only count as
# a calculation cue when the question also carries a real quantitative signal (operator,
# number+unit, two or more numbers, or a quantitative domain phrase). "tinh" is here
# because diacritic-stripping collides "tính"(compute) with "tỉnh"(province).
_BROAD_CALCULATION_MARKERS = {
    "tinh",
    "gia tri",
    "value",
    "bao nhieu",
    "how many",
    "how much",
    "combien",
    "cuanto",
    "cong thuc",
    "formula",
    "do co gian",
    "ty le",
    "ratio",
    "gdp",
}

_QUANTITATIVE_PHRASES = (
    "phuong trinh",
    "ham so",
    "dao ham",
    "xac suat",
    "lai suat",
    "thong ke",
    "dien tro",
    "cong suat",
    "tan so",
    "pka",
    "phuong sai",
    "lam phat",
    "van toc",
    "gia toc",
)
_LEGAL_ADMIN_MARKERS = (
    "can cuoc",
    "cong dan",
    "thu tuc",
    "ho so",
    "dang ky",
    "nop",
    "giay to",
    "van ban",
    "co quan",
    "cap tinh",
    "cap huyen",
    "cap xa",
)


def classify_problem(problem: Problem, config: HarnessConfig) -> ProblemProfile:
    thresholds = config.thresholds
    markers = config.markers
    full_text = normalize_text(problem.question)
    focus = focus_text(
        problem.question,
        markers["question"],
        thresholds["focus_tail_chars"],
    )

    calculation_hits, calculation_ignored = _marker_hits(
        focus,
        markers["calculation"],
        problem,
        kind="calculation",
    )
    negative_hits, negative_ignored = _marker_hits(
        focus,
        markers["negative"],
        problem,
        kind="negative",
    )
    context_hits, _ = _marker_hits(full_text, markers["context"], problem, kind="context")
    legal_admin_hits = _literal_hits(full_text, _LEGAL_ADMIN_MARKERS)

    has_many_choices = len(problem.choices) >= thresholds["many_choice_min"]
    has_calculation = bool(calculation_hits)
    has_negative = bool(negative_hits)
    has_long_context = len(problem.question) > thresholds["long_context_chars"] or bool(context_hits)
    has_legal_admin = bool(legal_admin_hits)

    features: list[str] = []
    reasons: list[str] = []
    diagnostics: list[str] = []
    if has_many_choices:
        features.append("has_many_choices")
        reasons.append("many_choices")
    if has_calculation:
        features.append("has_calculation")
        reasons.append(f"calculation_markers={','.join(calculation_hits)}")
    if has_negative:
        features.append("has_negative")
        reasons.append(f"negative_markers={','.join(negative_hits)}")
    if has_long_context:
        features.append("has_long_context")
        reasons.append("context_markers_or_long_text")
    if has_legal_admin:
        features.append("has_legal_admin")

    diagnostics.extend(f"ignored_calculation_marker={item}" for item in calculation_ignored)
    diagnostics.extend(f"ignored_negative_marker={item}" for item in negative_ignored)

    if has_negative:
        kind = "negative"
        prompt_variant = "elimination"
    elif has_calculation:
        kind = "calculation"
        prompt_variant = "calculation"
    elif has_many_choices:
        kind = "many_choice"
        prompt_variant = "elimination"
    elif has_long_context:
        kind = "reading"
        prompt_variant = "evidence"
    elif len(problem.question) < thresholds["short_question_chars"]:
        kind = "short"
        prompt_variant = "direct"
        reasons.append("short_question")
    else:
        kind = "general"
        prompt_variant = "direct"
        reasons.append("general_default")

    should_tournament = has_many_choices or has_calculation or has_negative
    should_verify = should_tournament or kind in {"reading", "general"}
    return ProblemProfile(
        kind=kind,
        reasons=tuple(reasons),
        prompt_variant=prompt_variant,
        should_verify=should_verify,
        should_tournament=should_tournament,
        features=tuple(features),
        diagnostics=tuple(diagnostics),
    )


def _marker_hits(
    normalized_text: str,
    markers: tuple[str, ...],
    problem: Problem,
    *,
    kind: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    hits: list[str] = []
    ignored: list[str] = []
    for marker in markers:
        normalized_marker = normalize_text(marker)
        if not _contains_phrase(normalized_text, normalized_marker):
            continue
        if kind == "calculation" and normalized_marker in _BROAD_CALCULATION_MARKERS:
            if not _has_quantitative_signal(problem, normalized_text):
                ignored.append(normalized_marker)
                continue
        if kind == "negative" and normalized_marker == "sai":
            if not _is_instructional_sai(normalized_text):
                ignored.append(normalized_marker)
                continue
        hits.append(normalized_marker)
    return tuple(dict.fromkeys(hits)), tuple(dict.fromkeys(ignored))


def _literal_hits(normalized_text: str, markers: tuple[str, ...]) -> tuple[str, ...]:
    hits = [
        marker
        for marker in markers
        if _contains_phrase(normalized_text, normalize_text(marker))
    ]
    return tuple(dict.fromkeys(hits))


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _has_quantitative_signal(problem: Problem, normalized_text: str) -> bool:
    """Language-agnostic test for a *real* computation, not just a stray digit.

    Evaluated on the question text only — answer choices routinely carry incidental
    digits (chemical formulas like CO2/H2O, years, article numbers) that must not be
    mistaken for arithmetic. A lone number is not enough; we require an arithmetic
    operator between numbers, a number with a unit, two or more numbers, or a
    quantitative domain phrase. Digits, operators and units are script-independent, so
    this works for any language.
    """
    if re.search(r"\d\s*[+\-*/=^×÷]\s*\d", normalized_text):
        return True
    if re.search(r"\d\s*%", normalized_text):
        return True
    if re.search(r"\d\s*(cm|mm|km|kg|mg|ml|hz|ohm|usd)\b", normalized_text):
        return True
    if len(re.findall(r"\d+", normalized_text)) >= 2:
        return True
    return any(_contains_phrase(normalized_text, phrase) for phrase in _QUANTITATIVE_PHRASES)


def _is_instructional_sai(normalized_text: str) -> bool:
    if _contains_phrase(normalized_text, "phuong sai"):
        return False
    return any(
        re.search(pattern, normalized_text) is not None
        for pattern in (
            r"\b(chon|hay chon|dap an|cau|y|dieu|noi dung|phat bieu|nhan dinh|khang dinh)\b.{0,90}\bsai\b",
            r"\bsai\b.{0,60}\b(nao|la|trong cac|sau day)\b",
        )
    )
