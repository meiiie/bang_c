from __future__ import annotations

from collections import Counter
from dataclasses import replace

from .classifier import classify_problem
from .config import HarnessConfig
from .evidence import adjudicate_direct_evidence
from .heuristic import fallback_answer
from .normalize import normalize_answer
from .nvidia_client import NvidiaChatClient
from .prompting import build_prompt, build_repair_prompt, build_verifier_prompt, tournament_variants
from .schema import Prediction, Problem, ProblemProfile, TraceStep


SolverStrategy = str


def solve_problem(
    problem: Problem,
    client: NvidiaChatClient | None,
    *,
    dry_run: bool = False,
    verify: bool = False,
    strategy: SolverStrategy = "auto",
    fail_fast: bool = False,
    config: HarnessConfig | None = None,
) -> Prediction:
    if config is None:
        from .config import load_config

        config = load_config()
    profile = classify_problem(problem, config)
    trace = (_classification_step(profile),)
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
            trace=trace
            + (
                TraceStep(
                    role="solver",
                    action="heuristic_fallback",
                    status="completed",
                    detail=f"dry_run={dry_run}",
                    answer=answer,
                ),
            ),
        )

    try:
        if strategy == "direct":
            return _with_trace(
                _solve_direct(problem, profile, client, config=config, verify=verify),
                trace,
            )
        if strategy == "verify":
            return _with_trace(
                _solve_direct(problem, profile, client, config=config, verify=True),
                trace,
            )
        if strategy == "tournament":
            return _with_trace(
                _solve_tournament(problem, profile, client, config=config, verify=verify),
                trace,
            )
        return _with_trace(
            _solve_auto(problem, profile, client, config=config, force_verify=verify),
            trace,
        )
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
            trace=trace
            + (
                TraceStep(
                    role="solver",
                    action="model_call",
                    status="blocked",
                    detail=error.__class__.__name__,
                ),
                TraceStep(
                    role="solver",
                    action="heuristic_fallback",
                    status="completed",
                    detail="fail_fast=false",
                    answer=answer,
                ),
            ),
        )


def _solve_auto(
    problem: Problem,
    profile: ProblemProfile,
    client: NvidiaChatClient,
    *,
    config: HarnessConfig,
    force_verify: bool,
) -> Prediction:
    if profile.should_tournament:
        return _solve_tournament(problem, profile, client, config=config, verify=True)
    return _solve_direct(
        problem,
        profile,
        client,
        config=config,
        verify=force_verify or profile.should_verify,
    )


def _solve_direct(
    problem: Problem,
    profile: ProblemProfile,
    client: NvidiaChatClient,
    *,
    config: HarnessConfig,
    verify: bool,
) -> Prediction:
    prompt = build_prompt(problem, profile, config=config)
    trace_steps: list[TraceStep] = []
    raw_answer = client.complete(
        prompt.system_prompt,
        prompt.user_prompt,
        max_tokens=prompt.max_tokens,
    )
    normalized = normalize_answer(raw_answer, problem)
    if normalized is None:
        trace_steps.append(
            TraceStep(
                role="solver",
                action=f"prompt:{prompt.variant}",
                status="warning",
                detail="model output was not a valid answer letter",
            )
        )
        repaired = _repair_invalid_answer(problem, client, raw_answer, config=config)
        if repaired is not None:
            raw_repair, repaired_answer = repaired
            trace_steps.append(
                TraceStep(
                    role="repair",
                    action="answer_only_repair",
                    status="completed",
                    detail="repair produced a valid answer letter",
                    answer=repaired_answer,
                )
            )
            return Prediction(
                qid=problem.qid,
                answer=repaired_answer,
                model=client.model,
                raw_answer=f"{prompt.variant}={raw_answer.strip()} | repair={raw_repair.strip()}",
                strategy="gemma_repaired",
                confidence=0.68,
                question_kind=profile.kind,
                prompt_variant=prompt.variant,
                attempts=2,
                trace=tuple(trace_steps),
            )
        return _fallback_prediction(
            problem,
            profile,
            client.model,
            raw_answer,
            f"invalid_{prompt.variant}",
            trace_steps=tuple(trace_steps),
        )

    trace_steps.append(
        TraceStep(
            role="solver",
            action=f"prompt:{prompt.variant}",
            status="completed",
            detail="model output normalized",
            answer=normalized,
        )
    )
    if verify:
        raw_verifier, verified = _verify(problem, client, normalized, config=config)
        if verified is not None:
            trace_steps.append(
                TraceStep(
                    role="verifier",
                    action="answer_only_check",
                    status="completed",
                    detail=_verification_detail(raw_verifier),
                    answer=verified,
                )
            )
            evidence_decision = adjudicate_direct_evidence(problem, verified, config)
            if evidence_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="evidence-adjudicator",
                        action="direct_passage_support",
                        status="warning",
                        detail=evidence_decision.detail,
                        answer=evidence_decision.answer,
                    )
                )
                return Prediction(
                    qid=problem.qid,
                    answer=evidence_decision.answer,
                    model=client.model,
                    raw_answer=(
                        f"{prompt.variant}={raw_answer.strip()} | "
                        f"verifier={raw_verifier.strip()} | "
                        f"direct_evidence={evidence_decision.answer}"
                    ),
                    strategy="gemma_verified_direct_evidence",
                    confidence=0.74,
                    question_kind=profile.kind,
                    prompt_variant=prompt.variant,
                    attempts=2,
                    trace=tuple(trace_steps),
                )
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
                trace=tuple(trace_steps),
            )
        trace_steps.append(
            TraceStep(
                role="verifier",
                action="answer_only_check",
                status="warning",
                detail="verifier output was not a valid answer letter",
            )
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
        trace=tuple(trace_steps),
    )


def _solve_tournament(
    problem: Problem,
    profile: ProblemProfile,
    client: NvidiaChatClient,
    *,
    config: HarnessConfig,
    verify: bool,
) -> Prediction:
    attempts: list[tuple[str, str, str | None]] = []
    trace_steps: list[TraceStep] = []
    for variant in tournament_variants(profile):
        prompt = build_prompt(problem, profile, config=config, variant=variant)
        raw_answer = client.complete(
            prompt.system_prompt,
            prompt.user_prompt,
            max_tokens=prompt.max_tokens,
        )
        normalized = normalize_answer(raw_answer, problem)
        attempts.append((variant, raw_answer, normalized))
        trace_steps.append(
            TraceStep(
                role="solver",
                action=f"tournament:{variant}",
                status="completed" if normalized else "warning",
                detail="variant output normalized"
                if normalized
                else "variant output was not a valid answer letter",
                answer=normalized,
            )
        )

    valid_answers = [answer for _, _, answer in attempts if answer is not None]
    if not valid_answers:
        raw = " | ".join(f"{variant}={raw.strip()}" for variant, raw, _ in attempts)
        return _fallback_prediction(
            problem,
            profile,
            client.model,
            raw,
            "invalid_tournament",
            trace_steps=tuple(trace_steps),
        )

    counts = Counter(valid_answers)
    answer, votes = counts.most_common(1)[0]
    confidence = 0.78 + min(0.15, 0.05 * (votes - 1))
    trace_steps.append(
        TraceStep(
            role="synthesizer",
            action="majority_vote",
            status="completed",
            detail=f"votes={votes}/{len(valid_answers)}",
            answer=answer,
        )
    )

    if verify or votes == 1:
        raw_verifier, verified = _verify(problem, client, answer, config=config)
        if verified is not None:
            attempts.append(("verifier", raw_verifier, verified))
            answer = verified
            confidence = max(confidence, 0.84 if verified in valid_answers else 0.70)
            trace_steps.append(
                TraceStep(
                    role="verifier",
                    action="answer_only_check",
                    status="completed",
                    detail=_verification_detail(raw_verifier),
                    answer=verified,
                )
            )
        else:
            trace_steps.append(
                TraceStep(
                    role="verifier",
                    action="answer_only_check",
                    status="warning",
                    detail="verifier output was not a valid answer letter",
                )
            )

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
        trace=tuple(trace_steps),
    )


def _verify(
    problem: Problem,
    client: NvidiaChatClient,
    candidate_answer: str,
    *,
    config: HarnessConfig,
) -> tuple[str, str | None]:
    prompt = build_verifier_prompt(problem, candidate_answer)
    raw_verifier = client.complete(
        prompt.system_prompt,
        prompt.user_prompt,
        max_tokens=prompt.max_tokens,
    )
    verified = normalize_answer(raw_verifier, problem)
    if verified is not None or not config.repair_invalid_output:
        return raw_verifier, verified
    repaired = _repair_invalid_answer(problem, client, raw_verifier, config=config)
    if repaired is None:
        return raw_verifier, None
    raw_repair, repaired_answer = repaired
    return f"{raw_verifier.strip()} | verifier_repair={raw_repair.strip()}", repaired_answer


def _verification_detail(raw_verifier: str) -> str:
    if "verifier_repair=" in raw_verifier:
        return "verifier output repaired to a valid answer letter"
    return "verifier returned a valid answer letter"


def _repair_invalid_answer(
    problem: Problem,
    client: NvidiaChatClient,
    invalid_answer: str,
    *,
    config: HarnessConfig,
) -> tuple[str, str] | None:
    if not config.repair_invalid_output:
        return None
    prompt = build_repair_prompt(problem, invalid_answer)
    raw_repair = client.complete(
        prompt.system_prompt,
        prompt.user_prompt,
        max_tokens=prompt.max_tokens,
    )
    repaired = normalize_answer(raw_repair, problem)
    if repaired is None:
        return None
    return raw_repair, repaired


def _fallback_prediction(
    problem: Problem,
    profile: ProblemProfile,
    model: str,
    raw_answer: str,
    reason: str,
    *,
    trace_steps: tuple[TraceStep, ...] = (),
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
        trace=trace_steps
        + (
            TraceStep(
                role="solver",
                action="heuristic_fallback",
                status="completed",
                detail=reason,
                answer=answer,
            ),
        ),
    )


def _classification_step(profile: ProblemProfile) -> TraceStep:
    detail = (
        f"kind={profile.kind}; variant={profile.prompt_variant}; "
        f"verify={profile.should_verify}; tournament={profile.should_tournament}"
    )
    if profile.reasons:
        detail = f"{detail}; reasons={','.join(profile.reasons)}"
    return TraceStep(
        role="classifier",
        action="profile_problem",
        status="completed",
        detail=detail,
    )


def _with_trace(prediction: Prediction, prefix: tuple[TraceStep, ...]) -> Prediction:
    return replace(prediction, trace=prefix + prediction.trace)
