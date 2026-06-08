from __future__ import annotations

from .heuristic import fallback_answer
from .normalize import normalize_answer
from .nvidia_client import NvidiaChatClient
from .prompting import SYSTEM_PROMPT, build_user_prompt, build_verifier_prompt
from .schema import Prediction, Problem


def solve_problem(
    problem: Problem,
    client: NvidiaChatClient | None,
    *,
    dry_run: bool = False,
    verify: bool = False,
) -> Prediction:
    if dry_run or client is None:
        answer, confidence, strategy = fallback_answer(problem)
        return Prediction(
            qid=problem.qid,
            answer=answer,
            model="heuristic",
            raw_answer=answer,
            strategy=strategy,
            confidence=confidence,
        )

    raw_answer = client.complete(SYSTEM_PROMPT, build_user_prompt(problem))
    normalized = normalize_answer(raw_answer, problem)
    if normalized is not None:
        if verify:
            raw_verifier = client.complete(
                SYSTEM_PROMPT,
                build_verifier_prompt(problem, normalized),
            )
            verified = normalize_answer(raw_verifier, problem)
            if verified is not None:
                return Prediction(
                    qid=problem.qid,
                    answer=verified,
                    model=client.model,
                    raw_answer=f"direct={raw_answer.strip()} | verifier={raw_verifier.strip()}",
                    strategy="gemma_verified",
                    confidence=0.85 if verified == normalized else 0.70,
                )
        return Prediction(
            qid=problem.qid,
            answer=normalized,
            model=client.model,
            raw_answer=raw_answer,
            strategy="gemma_direct",
            confidence=0.80,
        )

    answer, confidence, strategy = fallback_answer(problem)
    return Prediction(
        qid=problem.qid,
        answer=answer,
        model=client.model,
        raw_answer=raw_answer,
        strategy=f"{strategy}_after_invalid_llm",
        confidence=confidence,
    )
