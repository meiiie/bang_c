from __future__ import annotations

from collections import Counter

from .classifier import classify_problem
from .heuristic import fallback_answer
from .normalize import normalize_answer
from .nvidia_client import NvidiaChatClient
from .prompting import build_prompt, build_verifier_prompt, tournament_variants
from .schema import Prediction, Problem, ProblemProfile


SolverStrategy = str


def solve_problem(
    problem: Problem,
    client: NvidiaChatClient | None,
    *,
    dry_run: bool = False,
    verify: bool = False,
    strategy: SolverStrategy = "auto",
    fail_fast: bool = False,
) -> Prediction:
    profile = classify_problem(problem)
    if dry_run or client is None:
        answer, confidence, strategy = fallback_answer(problem)
        return Prediction(
            qid=problem.qid,
            answer=answer,
            model="heuristic",
            raw_answer=answer,
            strategy=strategy,
            confidence=confidence,
            question_kind=profile.kind,
            prompt_variant="heuristic",
        )

    try:
        if strategy == "direct":
            return _solve_direct(problem, profile, client, verify=verify)
        if strategy == "verify":
            return _solve_direct(problem, profile, client, verify=True)
        if strategy == "tournament":
            return _solve_tournament(problem, profile, client, verify=verify)
        return _solve_auto(problem, profile, client, force_verify=verify)
    except Exception as error:  # noqa: BLE001 - keep pred.csv complete by default
        if fail_fast:
            raise
        answer, confidence, fallback_strategy = fallback_answer(problem)
        return Prediction(
            qid=problem.qid,
            answer=answer,
            model=client.model,
            raw_answer=f"solver_error={error}",
            strategy=f"{fallback_strategy}_after_error",
            confidence=confidence,
            question_kind=profile.kind,
            prompt_variant=profile.prompt_variant,
            fallback_reason=error.__class__.__name__,
        )


def _solve_auto(
    problem: Problem,
    profile: ProblemProfile,
    client: NvidiaChatClient,
    *,
    force_verify: bool,
) -> Prediction:
    if profile.should_tournament:
        return _solve_tournament(problem, profile, client, verify=True)
    return _solve_direct(
        problem,
        profile,
        client,
        verify=force_verify or profile.should_verify,
    )


def _solve_direct(
    problem: Problem,
    profile: ProblemProfile,
    client: NvidiaChatClient,
    *,
    verify: bool,
) -> Prediction:
    prompt = build_prompt(problem, profile)
    raw_answer = client.complete(
        prompt.system_prompt,
        prompt.user_prompt,
        max_tokens=prompt.max_tokens,
    )
    normalized = normalize_answer(raw_answer, problem)
    if normalized is None:
        return _fallback_prediction(
            problem,
            profile,
            client.model,
            raw_answer,
            f"invalid_{prompt.variant}",
        )

    if verify:
        raw_verifier, verified = _verify(problem, client, normalized)
        if verified is not None:
            return Prediction(
                qid=problem.qid,
                answer=verified,
                model=client.model,
                raw_answer=f"{prompt.variant}={raw_answer.strip()} | verifier={raw_verifier.strip()}",
                strategy="gemma_verified",
                confidence=0.88 if verified == normalized else 0.72,
                question_kind=profile.kind,
                prompt_variant=prompt.variant,
                attempts=2,
            )

    return Prediction(
        qid=problem.qid,
        answer=normalized,
        model=client.model,
        raw_answer=raw_answer,
        strategy="gemma_direct",
        confidence=0.80,
        question_kind=profile.kind,
        prompt_variant=prompt.variant,
    )


def _solve_tournament(
    problem: Problem,
    profile: ProblemProfile,
    client: NvidiaChatClient,
    *,
    verify: bool,
) -> Prediction:
    attempts: list[tuple[str, str, str | None]] = []
    for variant in tournament_variants(profile):
        prompt = build_prompt(problem, profile, variant)
        raw_answer = client.complete(
            prompt.system_prompt,
            prompt.user_prompt,
            max_tokens=prompt.max_tokens,
        )
        attempts.append((variant, raw_answer, normalize_answer(raw_answer, problem)))

    valid_answers = [answer for _, _, answer in attempts if answer is not None]
    if not valid_answers:
        raw = " | ".join(f"{variant}={raw.strip()}" for variant, raw, _ in attempts)
        return _fallback_prediction(problem, profile, client.model, raw, "invalid_tournament")

    counts = Counter(valid_answers)
    answer, votes = counts.most_common(1)[0]
    confidence = 0.78 + min(0.15, 0.05 * (votes - 1))

    if verify or votes == 1:
        raw_verifier, verified = _verify(problem, client, answer)
        if verified is not None:
            attempts.append(("verifier", raw_verifier, verified))
            answer = verified
            confidence = max(confidence, 0.84 if verified in valid_answers else 0.70)

    raw = " | ".join(
        f"{variant}={raw.strip()}=>{normalized or '?'}"
        for variant, raw, normalized in attempts
    )
    return Prediction(
        qid=problem.qid,
        answer=answer,
        model=client.model,
        raw_answer=raw,
        strategy="gemma_tournament",
        confidence=confidence,
        question_kind=profile.kind,
        prompt_variant="+".join(tournament_variants(profile)),
        attempts=len(attempts),
    )


def _verify(
    problem: Problem,
    client: NvidiaChatClient,
    candidate_answer: str,
) -> tuple[str, str | None]:
    prompt = build_verifier_prompt(problem, candidate_answer)
    raw_verifier = client.complete(
        prompt.system_prompt,
        prompt.user_prompt,
        max_tokens=prompt.max_tokens,
    )
    return raw_verifier, normalize_answer(raw_verifier, problem)


def _fallback_prediction(
    problem: Problem,
    profile: ProblemProfile,
    model: str,
    raw_answer: str,
    reason: str,
) -> Prediction:
    answer, confidence, strategy = fallback_answer(problem)
    return Prediction(
        qid=problem.qid,
        answer=answer,
        model=model,
        raw_answer=raw_answer,
        strategy=f"{strategy}_after_invalid_llm",
        confidence=confidence,
        question_kind=profile.kind,
        prompt_variant=profile.prompt_variant,
        fallback_reason=reason,
    )
