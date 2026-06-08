from __future__ import annotations

import re
from dataclasses import dataclass

from .config import HarnessConfig
from .schema import Problem, ProblemProfile


SYSTEM_PROMPT = """You solve Vietnamese multiple-choice questions.
Rules:
- Use only the provided question and options.
- Select the best answer among the options.
- Return exactly one uppercase option letter.
- Do not include explanation, punctuation, or markdown."""


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str
    variant: str
    max_tokens: int = 12


def build_prompt(
    problem: Problem,
    profile: ProblemProfile,
    *,
    config: HarnessConfig,
    variant: str | None = None,
) -> PromptBundle:
    selected_variant = variant or profile.prompt_variant
    builder = {
        "direct": _direct_prompt,
        "evidence": _evidence_prompt,
        "elimination": _elimination_prompt,
        "calculation": _calculation_prompt,
    }.get(selected_variant, _direct_prompt)
    return PromptBundle(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=builder(problem, config),
        variant=selected_variant,
    )


def build_verifier_prompt(problem: Problem, candidate_answer: str) -> PromptBundle:
    candidate_text = ""
    if candidate_answer in problem.allowed_letters:
        index = problem.allowed_letters.index(candidate_answer)
        candidate_text = problem.choices[index]
    user_prompt = (
        "Verify the candidate answer for this Vietnamese multiple-choice item.\n"
        "Compare the candidate against every option. If it is correct, keep it. "
        "If another option is clearly better, return that other letter.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Candidate answer: {candidate_answer}. {candidate_text}\n\n"
        f"Return exactly one letter from: {_letters(problem)}"
    )
    return PromptBundle(SYSTEM_PROMPT, user_prompt, "verifier")


def tournament_variants(profile: ProblemProfile) -> tuple[str, ...]:
    if profile.kind == "calculation":
        return ("calculation", "direct")
    if profile.kind in {"many_choice", "negative"}:
        return ("elimination", "direct", "evidence")
    if profile.kind == "reading":
        return ("evidence", "direct")
    return ("direct", "evidence")


def _direct_prompt(problem: Problem, config: HarnessConfig) -> str:
    return (
        "Choose the best answer.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Return exactly one letter from: {_letters(problem)}"
    )


def _evidence_prompt(problem: Problem, config: HarnessConfig) -> str:
    context, query = _split_context_and_query(problem.question, config.markers["question"])
    if context:
        body = (
            "Read the context, then answer the question using only evidence in the context.\n\n"
            f"Context:\n{context}\n\n"
            f"Question:\n{query}\n\n"
            f"Options:\n{_format_options(problem)}\n\n"
        )
    else:
        body = (
            "Find the option that is best supported by the question text.\n\n"
            f"{_format_problem(problem)}\n\n"
        )
    return body + f"Return exactly one letter from: {_letters(problem)}"


def _elimination_prompt(problem: Problem, config: HarnessConfig) -> str:
    return (
        "Choose by elimination. Pay close attention to negative wording such as "
        "'khong dung', 'khong phai', 'ngoai tru', and 'sai'.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Return exactly one letter from: {_letters(problem)}"
    )


def _calculation_prompt(problem: Problem, config: HarnessConfig) -> str:
    return (
        "Solve the quantitative or logical question carefully. Use the numbers "
        "in the prompt, compare with the options, then return the matching letter.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Return exactly one letter from: {_letters(problem)}"
    )


def _format_problem(problem: Problem) -> str:
    return f"Question:\n{problem.question}\n\nOptions:\n{_format_options(problem)}"


def _format_options(problem: Problem) -> str:
    return "\n".join(
        f"{letter}. {choice}"
        for letter, choice in zip(problem.allowed_letters, problem.choices, strict=False)
    )


def _letters(problem: Problem) -> str:
    return ", ".join(problem.allowed_letters)


def _split_context_and_query(question: str, markers: tuple[str, ...]) -> tuple[str, str]:
    patterns = [rf"\n\s*{re.escape(marker)}" for marker in markers]
    patterns.extend(
        (
            r"\n\s*Câu hỏi\s*:",
            r"\n\s*Question\s*:",
            r"\n\s*Pregunta\s*:",
            r"\n\s*Question\s*:",
        )
    )
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            context = question[: match.start()].strip()
            query = question[match.end() :].strip()
            if context and query:
                return context, query
    return "", question.strip()
