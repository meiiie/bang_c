from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

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


REASONING_SYSTEM_PROMPT = """You are a careful exam solver for multiple-choice questions.
The question may be written in any language (Vietnamese, English, Chinese, Korean, ...).
Read it in its own language; do not assume any particular language.
Think step by step to find the single best option. Pay attention to:
- negation (words meaning "not", "incorrect", "except", "false") — these flip the target;
- any calculation the question requires — compute it before comparing to the options.
Use only the information in the question and its options.
Finish with a final line in exactly this format:
ANSWER: <letter>
where <letter> is one of the available option letters."""


SAFETY_REFUSAL_CLAUSE = (
    "\n\nSafety rule: if the question asks HOW to carry out an illegal or harmful act "
    "(for example: violate a ban or suspension, falsify documents or labels, evade or "
    "withhold information from the authorities, leak classified material, sabotage, or "
    "abuse power to corrupt), then the correct option is the one that REFUSES to help "
    "(e.g. \"Tôi không thể trả lời/cung cấp...\", \"I cannot...\", \"outside the scope\"). "
    "For a legitimate question, NEVER choose a refusal option, and never choose an "
    "\"all of the above\" option when the list contains a refusal option. Judge by the "
    "meaning of the request, not by keywords."
)


def with_safety_clause(bundle: "PromptBundle", enabled: bool) -> "PromptBundle":
    """Append the safety-refusal clause to a bundle's system prompt when enabled.

    Applied once at the voting layer so it covers every reasoning path (self-
    consistency, reading, rag) without touching each builder. No-op when disabled,
    so the default contest path is byte-for-byte unchanged.
    """
    if not enabled:
        return bundle
    return replace(bundle, system_prompt=bundle.system_prompt + SAFETY_REFUSAL_CLAUSE)


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str
    variant: str
    max_tokens: int = 96


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
    return PromptBundle(SYSTEM_PROMPT, user_prompt, "verifier", max_tokens=64)


def build_tiebreak_prompt(problem: Problem, tied_answers: tuple[str, ...]) -> PromptBundle:
    tied_options = []
    for letter in tied_answers:
        if letter in problem.allowed_letters:
            index = problem.allowed_letters.index(letter)
            tied_options.append(f"{letter}. {problem.choices[index]}")
    user_prompt = (
        "Break the tie between candidate answers for this multiple-choice item.\n"
        "Do not assume the first candidate is correct. Compare the tied options "
        "against the question and all answer choices from scratch.\n"
        "Return only the best tied answer letter.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Tied candidates:\n{chr(10).join(tied_options)}\n\n"
        f"Return exactly one letter from: {', '.join(tied_answers)}"
    )
    return PromptBundle(SYSTEM_PROMPT, user_prompt, "tiebreak", max_tokens=64)


def build_repair_prompt(problem: Problem, invalid_answer: str) -> PromptBundle:
    user_prompt = (
        "Your previous response did not follow the required format.\n"
        "Return only the single best option letter. No words. No explanation.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Previous invalid response:\n{invalid_answer[:600]}\n\n"
        f"Valid letters: {_letters(problem)}"
    )
    return PromptBundle(SYSTEM_PROMPT, user_prompt, "repair", max_tokens=16)


def _exemplar_parts(exemplars: tuple[dict, ...]) -> list[str]:
    """Format few-shot exemplars as prompt sections (shared by the reasoning and
    reading prompts). Empty exemplars -> no sections."""
    if not exemplars:
        return []
    parts = [
        "Here are solved examples showing the expected reasoning and answer format:"
    ]
    for exemplar in exemplars:
        example_problem = Problem(
            qid="exemplar",
            question=str(exemplar["question"]),
            choices=tuple(str(choice) for choice in exemplar["choices"]),
        )
        block = _format_problem(example_problem)
        reasoning = str(exemplar.get("reasoning", "")).strip()
        answer_line = f"ANSWER: {exemplar['answer']}"
        parts.append(
            f"{block}\n\n{reasoning}\n{answer_line}" if reasoning else f"{block}\n\n{answer_line}"
        )
    parts.append("Now solve the real question:")
    return parts


def build_reasoning_prompt(
    problem: Problem,
    *,
    max_tokens: int = 512,
    exemplars: tuple[dict, ...] = (),
) -> PromptBundle:
    """Reasoning prompt, optionally few-shot.

    Exemplars are demonstrations in the question's own language (evidence: native-
    language exemplars + English meta-instructions is the strongest combination for
    Vietnamese exam MCQ). Each exemplar dict: question, choices (list), answer, and
    an optional short `reasoning` string shown before the answer line.
    """
    parts: list[str] = _exemplar_parts(exemplars)
    parts.append(
        "Solve this multiple-choice question. Reason briefly, then commit to one letter.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Available letters: {_letters(problem)}\n"
        "End your answer with a line: ANSWER: <letter>"
    )
    user_prompt = "\n\n---\n\n".join(parts)
    return PromptBundle(REASONING_SYSTEM_PROMPT, user_prompt, "reasoning", max_tokens=max_tokens)


READING_SYSTEM_PROMPT = """You answer multiple-choice questions about a supplied passage.
The passage and question may be in any language; read them in their own language.
The correct option is the one the PASSAGE supports — not the one that is merely true.
Reject these distractor traps:
- an option that is true in general but does not answer THIS question;
- an option that attributes a fact to the wrong source, author, person, or section;
- an option that claims more than the passage actually states (outside inference).
Watch for negation (words meaning "not", "incorrect", "except", "false") — it flips
the target: the answer is then the option the passage does NOT support.
Ground every judgement in the passage text itself, not outside knowledge.
If no passage is supplied with the question, answer from your own knowledge instead.
Finish with a final line in exactly this format:
ANSWER: <letter>
where <letter> is one of the available option letters."""


def build_reading_prompt(
    problem: Problem,
    *,
    max_tokens: int = 512,
    exemplars: tuple[dict, ...] = (),
) -> PromptBundle:
    """Passage-grounded reading prompt — the reading analog of TIR: TIR grounds the
    answer on executed Python output, this grounds it on a quoted passage span.

    Targets the distractor traps observed in the real test (true-but-off-topic options,
    wrong-source attribution, inference beyond the passage). Same signature as
    build_reasoning_prompt so the self-consistency sampling loop can use either builder.
    """
    parts: list[str] = _exemplar_parts(exemplars)
    parts.append(
        "Answer this multiple-choice question about the supplied passage.\n\n"
        f"{_format_problem(problem)}\n\n"
        "Work strictly from the passage:\n"
        "1. Quote the exact sentence(s) from the passage that answer the question.\n"
        "2. Check every option against the passage, one by one. Reject an option if it "
        "is true but does not answer this question, if it cites the wrong source or "
        "attribution, or if it claims something the passage does not state.\n"
        "3. Choose the option whose full claim is directly supported by your quoted "
        "sentence(s).\n"
        "For a negated question (which option is NOT stated / incorrect / except): "
        "verify passage support for every option and choose the one WITHOUT support.\n"
        "If no passage is supplied, skip the quoting and answer from your own "
        "knowledge.\n\n"
        f"Available letters: {_letters(problem)}\n"
        "End your answer with a line: ANSWER: <letter>"
    )
    user_prompt = "\n\n---\n\n".join(parts)
    return PromptBundle(READING_SYSTEM_PROMPT, user_prompt, "reading", max_tokens=max_tokens)


RAG_SYSTEM_PROMPT = """You answer multiple-choice questions with the help of retrieved
reference excerpts. The question may be in any language; read it in its own language.
The excerpts come from an AUTOMATIC search and may be irrelevant or incomplete:
- if an excerpt directly answers the question, ground your answer on its wording;
- if the excerpts do not answer the question, rely on your own knowledge instead;
- never let an irrelevant excerpt talk you out of a fact you know.
Watch for negation (words meaning "not", "incorrect", "except", "false") — it flips
the target.
Finish with a final line in exactly this format:
ANSWER: <letter>
where <letter> is one of the available option letters."""


def build_rag_prompt(
    problem: Problem,
    snippets: tuple,
    *,
    max_tokens: int = 512,
    exemplars: tuple[dict, ...] = (),
) -> PromptBundle:
    """Retrieval-grounded prompt for the legal/admin factual slice.

    Retrieved excerpts are presented as fallible references, never as ground truth:
    retrieval is automatic and the corpus is narrow, so the model must stay free to
    answer from its own knowledge when the excerpts miss (the same graceful-degradation
    contract the reading prompt uses for missing passages). Snippet text is capped so a
    long statute chunk cannot crowd out the question; the cap matches the corpus-build
    chunk size (so it rarely fires), cuts on whitespace, and marks the cut visibly —
    the model must be able to tell a truncated excerpt from a complete short one."""
    references = "\n\n".join(
        f"[{index + 1}] {snippet.title}\n{_cap_text(snippet.text, 1500)}".strip()
        for index, snippet in enumerate(snippets)
    )
    parts: list[str] = _exemplar_parts(exemplars)
    parts.append(
        "Reference excerpts (automatic search results — may be irrelevant):\n\n"
        f"{references}\n\n"
        "Solve this multiple-choice question. Use the excerpts when they answer the "
        "question; otherwise use your own knowledge.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Available letters: {_letters(problem)}\n"
        "End your answer with a line: ANSWER: <letter>"
    )
    user_prompt = "\n\n---\n\n".join(parts)
    return PromptBundle(RAG_SYSTEM_PROMPT, user_prompt, "rag", max_tokens=max_tokens)


def _cap_text(text: str, limit: int) -> str:
    """Cap on a whitespace boundary with a visible truncation marker."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip() + " […]"


TIR_SYSTEM_PROMPT = """You solve quantitative multiple-choice questions by writing and \
running a short Python program. The question may be in any language.
Write ONE self-contained Python 3 program (standard library only) that computes the \
quantity the question asks for and prints the final numeric result clearly.
Rules:
- Put the program in a single ```python ... ``` code block.
- Use only the numbers and relationships stated in the question; show the final value with print().
- Do not guess an option letter yet — just compute and print the result.
Return only the reasoning needed to set up the computation, then the code block."""


def build_tir_code_prompt(problem: Problem, *, max_tokens: int = 1024) -> PromptBundle:
    """Round 1 of tool-integrated reasoning: ask for a Python program that computes the
    answer. The model must NOT pick a letter yet — it computes a numeric result that the
    follow-up round maps onto the options (separates correct computation from option-matching)."""
    user_prompt = (
        "Solve this quantitative question by writing a Python program that computes the "
        "required value.\n\n"
        f"{_format_problem(problem)}\n\n"
        "Write a single self-contained ```python``` program (standard library only) that "
        "computes the answer and prints the final numeric result. Do not select an option "
        "letter yet."
    )
    return PromptBundle(TIR_SYSTEM_PROMPT, user_prompt, "tir_code", max_tokens=max_tokens)


def build_tir_answer_prompt(
    problem: Problem, code: str, execution_output: str, *, max_tokens: int = 96
) -> PromptBundle:
    """Round 2 of TIR: given the program's executed output, pick the matching option letter."""
    output = execution_output.strip() or "(no output)"
    user_prompt = (
        "You wrote a Python program to solve this question and it has been executed.\n\n"
        f"{_format_problem(problem)}\n\n"
        f"Your program:\n```python\n{code[:2000]}\n```\n\n"
        f"Execution output:\n{output[:1500]}\n\n"
        "Using the computed result, choose the option whose value matches it most closely. "
        "If the output looks wrong or errored, fall back to your best reasoning.\n"
        f"Available letters: {_letters(problem)}\n"
        "End with a line: ANSWER: <letter>"
    )
    return PromptBundle(REASONING_SYSTEM_PROMPT, user_prompt, "tir_answer", max_tokens=max_tokens)


@lru_cache(maxsize=8)
def load_exemplars(path: str) -> tuple[dict, ...]:
    """Load few-shot exemplars from a JSON list file; empty path -> no exemplars."""
    if not path:
        return ()
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"Few-shot exemplar file not found: {file_path}")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Exemplar file must be a JSON list: {file_path}")
    exemplars: list[dict] = []
    for index, row in enumerate(data):
        if not isinstance(row, dict) or not all(
            key in row for key in ("question", "choices", "answer")
        ):
            raise ValueError(f"Exemplar {index} must have question/choices/answer: {file_path}")
        exemplars.append(row)
    return tuple(exemplars)


def tournament_variants(profile: ProblemProfile) -> tuple[str, ...]:
    features = set(profile.features)
    if "has_calculation" in features and "has_many_choices" in features:
        return ("calculation", "direct", "elimination")
    if "has_calculation" in features or profile.kind == "calculation":
        return ("calculation", "direct")
    if "has_negative" in features or profile.kind in {"many_choice", "negative"}:
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
