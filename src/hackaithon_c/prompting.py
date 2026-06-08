from __future__ import annotations

import re
from dataclasses import dataclass

from .config import HarnessConfig
from .schema import Problem, ProblemProfile


SYSTEM_PROMPT = """You solve Vietnamese multiple-choice questions.
Rules:
- Use only the provided question and options.
- Select the best answer among the options.
- For passage questions, prefer the option with the strongest direct evidence
  in the provided passage, not outside knowledge.
- If multiple options are factually true, choose the one whose full claim is
  explicitly supported by the passage text.
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
        "Verify the candidate answer for this Vietnamese multiple-choice item as a "
        "passage-grounded adjudicator.\n"
        "Compare the candidate against every option using only the supplied question, "
        "context, and options.\n"
        "If more than one option is factually true, prefer the option whose complete "
        "claim is stated most directly in the provided passage.\n"
        "Do not reward an option that requires outside knowledge, cross-section "
        "wording, or inference when another option has a clearer evidence span.\n"
        "If the candidate is correct by background knowledge but another option is "
        "better supported by the passage wording, return the better-supported letter.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Candidate answer: {candidate_answer}. {candidate_text}\n\n"
        f"Return exactly one letter from: {_letters(problem)}"
    )
    return PromptBundle(SYSTEM_PROMPT, user_prompt, "verifier")


def build_repair_prompt(problem: Problem, invalid_answer: str) -> PromptBundle:
    user_prompt = (
        "Your previous response did not follow the required format.\n"
        "Return only the single best option letter. No words. No explanation.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Previous invalid response:\n{invalid_answer[:600]}\n\n"
        f"Valid letters: {_letters(problem)}"
    )
    return PromptBundle(SYSTEM_PROMPT, user_prompt, "repair", max_tokens=4)


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
            "Read the context, then answer the question using only evidence in the context.\n"
            "If several options are true in general, choose the option whose full claim "
            "has the clearest direct evidence span in the context.\n"
            "Avoid choosing an option that needs outside knowledge or combines wording "
            "from different sections when another option is directly stated.\n\n"
            f"Context:\n{context}\n\n"
            f"Question:\n{query}\n\n"
            f"Options:\n{_format_options(problem)}\n\n"
        )
    else:
        body = (
            "Find the option that is best supported by the question text.\n"
            "If several options are true in general, choose the one most directly "
            "supported by the supplied text.\n\n"
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
