from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace

from .calculation import adjudicate_calculation
from .calibration import agreement_confidence, majority_vote, vote_distribution
from .classifier import classify_problem
from .config import HarnessConfig
from .evidence import adjudicate_date_evidence, adjudicate_direct_evidence
from .heuristic import fallback_answer
from .model_client import ChatClient
from .normalize import normalize_answer
from .permute import (
    original_letter,
    rotate_problem,
    rotation_for_sample,
    stable_seed,
)
from .prompting import (
    build_prompt,
    build_rag_prompt,
    build_reading_prompt,
    build_reasoning_prompt,
    build_repair_prompt,
    build_tiebreak_prompt,
    build_tir_answer_prompt,
    build_tir_code_prompt,
    build_verifier_prompt,
    load_exemplars,
    tournament_variants,
    with_safety_clause,
)
from .principles import adjudicate_principle
from .retrieval import cached_retriever
from .schema import Prediction, Problem, ProblemProfile, TraceStep
from .tool_runtime import extract_code, run_python


SolverStrategy = str

# Agreement at or above this fraction is treated as a confident self-consistency vote;
# below it the item is flagged (warning) as an escalation candidate for later phases.
_CONFIDENT_AGREEMENT = 0.6


def solve_problem(
    problem: Problem,
    client: ChatClient | None,
    *,
    dry_run: bool = False,
    verify: bool = False,
    strategy: SolverStrategy = "auto",
    fail_fast: bool = False,
    config: HarnessConfig | None = None,
    challenger: ChatClient | None = None,
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
        if strategy == "self_consistency":
            return _with_trace(
                _solve_self_consistency(problem, profile, client, config=config),
                trace,
            )
        if strategy == "tiered":
            return _with_trace(
                _solve_tiered(problem, profile, client, config=config, challenger=challenger),
                trace,
            )
        if strategy == "tir":
            return _with_trace(
                _solve_tir(problem, profile, client, config=config),
                trace,
            )
        if strategy == "reading":
            return _with_trace(
                _solve_reading(problem, profile, client, config=config),
                trace,
            )
        if strategy == "rag":
            return _with_trace(
                _solve_rag(problem, profile, client, config=config),
                trace,
            )
        if strategy == "router":
            return _with_trace(
                _solve_router(problem, profile, client, config=config, challenger=challenger),
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
    client: ChatClient,
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
    client: ChatClient,
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
            calculation_decision = adjudicate_calculation(problem)
            if calculation_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="calculation-adjudicator",
                        action="deterministic_formula_check",
                        status="warning"
                        if calculation_decision.answer != repaired_answer
                        else "completed",
                        detail=calculation_decision.detail,
                        answer=calculation_decision.answer,
                    )
                )
                return Prediction(
                    qid=problem.qid,
                    answer=calculation_decision.answer,
                    model=client.model,
                    raw_answer=(
                        f"{prompt.variant}={raw_answer.strip()} | "
                        f"repair={raw_repair.strip()} | "
                        f"calculation={calculation_decision.answer}"
                    ),
                    strategy="gemma_repaired_calculation",
                    confidence=0.82,
                    question_kind=profile.kind,
                    prompt_variant=prompt.variant,
                    attempts=2,
                    trace=tuple(trace_steps),
                )
            principle_decision = adjudicate_principle(problem)
            if principle_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="principle-adjudicator",
                        action="domain_principle_check",
                        status="warning"
                        if principle_decision.answer != repaired_answer
                        else "completed",
                        detail=principle_decision.detail,
                        answer=principle_decision.answer,
                    )
                )
                return Prediction(
                    qid=problem.qid,
                    answer=principle_decision.answer,
                    model=client.model,
                    raw_answer=(
                        f"{prompt.variant}={raw_answer.strip()} | "
                        f"repair={raw_repair.strip()} | "
                        f"principle={principle_decision.answer}"
                    ),
                    strategy="gemma_repaired_principle",
                    confidence=0.82,
                    question_kind=profile.kind,
                    prompt_variant=prompt.variant,
                    attempts=2,
                    trace=tuple(trace_steps),
                )
            if verify:
                raw_verifier, verified = _verify(
                    problem,
                    client,
                    repaired_answer,
                    config=config,
                )
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
                    return Prediction(
                        qid=problem.qid,
                        answer=verified,
                        model=client.model,
                        raw_answer=(
                            f"{prompt.variant}={raw_answer.strip()} | "
                            f"repair={raw_repair.strip()} | verifier={raw_verifier.strip()}"
                        ),
                        strategy="gemma_repaired_verified",
                        confidence=0.74 if verified != repaired_answer else 0.78,
                        question_kind=profile.kind,
                        prompt_variant=prompt.variant,
                        attempts=3,
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
        evidence_decision = adjudicate_date_evidence(problem, None, config)
        if evidence_decision is not None:
            trace_steps.append(
                TraceStep(
                    role="evidence-adjudicator",
                    action="date_passage_support",
                    status="warning",
                    detail=evidence_decision.detail,
                    answer=evidence_decision.answer,
                )
            )
            return Prediction(
                qid=problem.qid,
                answer=evidence_decision.answer,
                model=client.model,
                raw_answer=f"{prompt.variant}={raw_answer.strip()} | date_evidence={evidence_decision.answer}",
                strategy="gemma_date_evidence",
                confidence=0.76,
                question_kind=profile.kind,
                prompt_variant=prompt.variant,
                attempts=1,
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
            calculation_decision = adjudicate_calculation(problem)
            if calculation_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="calculation-adjudicator",
                        action="deterministic_formula_check",
                        status="warning"
                        if calculation_decision.answer != verified
                        else "completed",
                        detail=calculation_decision.detail,
                        answer=calculation_decision.answer,
                    )
                )
                return Prediction(
                    qid=problem.qid,
                    answer=calculation_decision.answer,
                    model=client.model,
                    raw_answer=(
                        f"{prompt.variant}={raw_answer.strip()} | "
                        f"verifier={raw_verifier.strip()} | "
                        f"calculation={calculation_decision.answer}"
                    ),
                    strategy="gemma_verified_calculation",
                    confidence=0.86
                    if calculation_decision.answer == verified
                    else 0.76,
                    question_kind=profile.kind,
                    prompt_variant=prompt.variant,
                    attempts=2,
                    trace=tuple(trace_steps),
                )
            principle_decision = adjudicate_principle(problem)
            if principle_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="principle-adjudicator",
                        action="domain_principle_check",
                        status="warning"
                        if principle_decision.answer != verified
                        else "completed",
                        detail=principle_decision.detail,
                        answer=principle_decision.answer,
                    )
                )
                return Prediction(
                    qid=problem.qid,
                    answer=principle_decision.answer,
                    model=client.model,
                    raw_answer=(
                        f"{prompt.variant}={raw_answer.strip()} | "
                        f"verifier={raw_verifier.strip()} | "
                        f"principle={principle_decision.answer}"
                    ),
                    strategy="gemma_verified_principle",
                    confidence=0.86
                    if principle_decision.answer == verified
                    else 0.76,
                    question_kind=profile.kind,
                    prompt_variant=prompt.variant,
                    attempts=2,
                    trace=tuple(trace_steps),
                )
            evidence_decision = adjudicate_date_evidence(
                problem,
                verified,
                config,
            ) or adjudicate_direct_evidence(problem, verified, config)
            if evidence_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="evidence-adjudicator",
                        action="passage_support",
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
                raw_answer=(
                    f"{prompt.variant}={raw_answer.strip()} | "
                    f"verifier={raw_verifier.strip()}"
                ),
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

    calculation_decision = adjudicate_calculation(problem)
    if calculation_decision is not None:
        trace_steps.append(
            TraceStep(
                role="calculation-adjudicator",
                action="deterministic_formula_check",
                status="warning"
                if calculation_decision.answer != normalized
                else "completed",
                detail=calculation_decision.detail,
                answer=calculation_decision.answer,
            )
        )
        return Prediction(
            qid=problem.qid,
            answer=calculation_decision.answer,
            model=client.model,
            raw_answer=(
                f"{prompt.variant}={raw_answer.strip()} | "
                f"calculation={calculation_decision.answer}"
            ),
            strategy="gemma_direct_calculation",
            confidence=0.80 if calculation_decision.answer == normalized else 0.70,
            question_kind=profile.kind,
            prompt_variant=prompt.variant,
            trace=tuple(trace_steps),
        )

    principle_decision = adjudicate_principle(problem)
    if principle_decision is not None:
        trace_steps.append(
            TraceStep(
                role="principle-adjudicator",
                action="domain_principle_check",
                status="warning"
                if principle_decision.answer != normalized
                else "completed",
                detail=principle_decision.detail,
                answer=principle_decision.answer,
            )
        )
        return Prediction(
            qid=problem.qid,
            answer=principle_decision.answer,
            model=client.model,
            raw_answer=(
                f"{prompt.variant}={raw_answer.strip()} | "
                f"principle={principle_decision.answer}"
            ),
            strategy="gemma_direct_principle",
            confidence=0.80 if principle_decision.answer == normalized else 0.70,
            question_kind=profile.kind,
            prompt_variant=prompt.variant,
            trace=tuple(trace_steps),
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
    client: ChatClient,
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
        variant_raw = raw_answer
        detail = "variant output normalized"
        if normalized is None:
            repaired = _repair_invalid_answer(problem, client, raw_answer, config=config)
            if repaired is not None:
                raw_repair, repaired_answer = repaired
                variant_raw = f"{raw_answer.strip()} | repair={raw_repair.strip()}"
                normalized = repaired_answer
                detail = "variant output repaired to a valid answer letter"
            else:
                detail = "variant output was not a valid answer letter"
        attempts.append((variant, variant_raw, normalized))
        trace_steps.append(
            TraceStep(
                role="solver",
                action=f"tournament:{variant}",
                status="completed" if normalized else "warning",
                detail=detail,
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
    votes = max(counts.values())
    tied_answers = tuple(
        answer
        for answer in problem.allowed_letters
        if counts.get(answer, 0) == votes
    )
    answer = tied_answers[0]
    distribution = ",".join(
        f"{letter}:{counts[letter]}"
        for letter in problem.allowed_letters
        if counts.get(letter)
    )
    tie = len(tied_answers) > 1
    confidence = 0.72 if tie else 0.78 + min(0.15, 0.05 * (votes - 1))
    detail = f"votes={votes}/{len(valid_answers)}; distribution={distribution}"
    if tie:
        detail = f"{detail}; tied={','.join(tied_answers)}"
    trace_steps.append(
        TraceStep(
            role="synthesizer",
            action="majority_vote",
            status="warning" if tie else "completed",
            detail=detail,
            answer=answer,
        )
    )

    if tie:
        raw_tiebreak, tiebreak = _break_tie(
            problem,
            client,
            tied_answers,
        )
        if tiebreak in tied_answers:
            attempts.append(("tiebreak", raw_tiebreak, tiebreak))
            answer = tiebreak
            confidence = max(confidence, 0.76)
            trace_steps.append(
                TraceStep(
                    role="tie-breaker",
                    action="answer_only_check",
                    status="completed",
                    detail="tie-breaker selected a tied answer",
                    answer=tiebreak,
                )
            )
        else:
            trace_steps.append(
                TraceStep(
                    role="tie-breaker",
                    action="answer_only_check",
                    status="warning",
                    detail="tie-breaker output was not one of the tied answers",
                )
            )

    if verify or tie or votes == 1:
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

    calculation_decision = adjudicate_calculation(problem)
    if calculation_decision is not None:
        trace_steps.append(
            TraceStep(
                role="calculation-adjudicator",
                action="deterministic_formula_check",
                status="warning"
                if calculation_decision.answer != answer
                else "completed",
                detail=calculation_decision.detail,
                answer=calculation_decision.answer,
            )
        )
        answer = calculation_decision.answer
        confidence = max(confidence, 0.82)
        attempts.append(("calculation", calculation_decision.detail, answer))
    else:
        principle_decision = adjudicate_principle(problem)
        if principle_decision is not None:
            trace_steps.append(
                TraceStep(
                    role="principle-adjudicator",
                    action="domain_principle_check",
                    status="warning"
                    if principle_decision.answer != answer
                    else "completed",
                    detail=principle_decision.detail,
                    answer=principle_decision.answer,
                )
            )
            answer = principle_decision.answer
            confidence = max(confidence, 0.82)
            attempts.append(("principle", principle_decision.detail, answer))
        else:
            evidence_decision = adjudicate_date_evidence(
                problem,
                answer,
                config,
            ) or adjudicate_direct_evidence(problem, answer, config)
            if evidence_decision is not None:
                trace_steps.append(
                    TraceStep(
                        role="evidence-adjudicator",
                        action="passage_support",
                        status="warning",
                        detail=evidence_decision.detail,
                        answer=evidence_decision.answer,
                    )
                )
                answer = evidence_decision.answer
                confidence = max(confidence, 0.74)
                attempts.append(("direct_evidence", evidence_decision.detail, answer))

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


def _collect_reasoning_votes(
    problem: Problem,
    client: ChatClient,
    samples: int,
    *,
    config: HarnessConfig,
    label: str,
    diversify: bool = False,
    start_index: int = 0,
    prompt_builder=build_reasoning_prompt,
) -> tuple[list[str], list[TraceStep]]:
    """Sample `samples` reasoned answers from one client; return (answers, trace_steps).

    Answers are always reported in the ORIGINAL letter space. With `diversify`,
    sample 0 stays the deterministic anchor while later samples (a) see cyclically
    rotated choice orders (position-bias debiasing) and (b) sample at
    `reasoning_temperature` with a stable per-(qid, index) seed, so runs remain
    reproducible. A sample that yields no letter gets one deterministic repair pass
    (same `repair_invalid_output` gate the tournament path uses). `prompt_builder`
    swaps the per-sample prompt (e.g. build_reading_prompt) while keeping the same
    rotation/sampling/repair machinery.
    """
    answers: list[str] = []
    trace_steps: list[TraceStep] = []
    exemplars = load_exemplars(config.reasoning_few_shot_path)
    for offset in range(max(1, samples)):
        index = start_index + offset
        rotation = rotation_for_sample(index, len(problem.choices)) if diversify else 0
        sample_problem = rotate_problem(problem, rotation)
        prompt = with_safety_clause(
            prompt_builder(
                sample_problem,
                max_tokens=config.reasoning_max_tokens,
                exemplars=exemplars,
            ),
            config.enable_safety_refusal,
        )
        sampling: dict[str, float | int] = {}
        if diversify and index > 0:
            sampling = {
                "temperature": config.reasoning_temperature,
                "top_p": config.reasoning_top_p,
                "top_k": config.reasoning_top_k,
                "seed": stable_seed(problem.qid, index),
            }
        raw_answer = client.complete(
            prompt.system_prompt,
            prompt.user_prompt,
            max_tokens=prompt.max_tokens,
            **sampling,
        )
        normalized = normalize_answer(raw_answer, sample_problem)
        detail = "sample produced a valid answer letter"
        if normalized is None:
            repaired = _repair_invalid_answer(sample_problem, client, raw_answer, config=config)
            if repaired is not None:
                _, normalized = repaired
                detail = "sample repaired to a valid answer letter"
            else:
                detail = "sample produced no valid answer letter"
        mapped = original_letter(normalized, rotation, problem) if normalized else None
        if rotation:
            detail = f"{detail}; rotation={rotation}"
        answers.append(mapped or "")
        trace_steps.append(
            TraceStep(
                role="solver",
                action=f"{label}:{index + 1}",
                status="completed" if mapped else "warning",
                detail=detail,
                answer=mapped,
            )
        )
    return answers, trace_steps


def _vote_prediction(
    problem: Problem,
    profile: ProblemProfile,
    model: str,
    answers: list[str],
    trace_steps: list[TraceStep],
    *,
    strategy: str,
    fallback_reason: str,
    variant: str = "reasoning",
) -> Prediction:
    """Turn collected votes into a Prediction with agreement-based confidence, or fall
    back if no sample produced a valid letter. `variant` labels which prompt the
    samples used (measurement metadata only)."""
    winner, votes, total = majority_vote(answers)
    if winner is None:
        raw = " | ".join(f"s{index + 1}={answer or '?'}" for index, answer in enumerate(answers))
        return _fallback_prediction(
            problem, profile, model, raw, fallback_reason, trace_steps=tuple(trace_steps)
        )
    confidence = agreement_confidence(votes, total)
    distribution = vote_distribution(answers)
    steps = list(trace_steps)
    steps.append(
        TraceStep(
            role="synthesizer",
            action="agreement_vote",
            status="completed" if confidence >= _CONFIDENT_AGREEMENT else "warning",
            detail=f"winner={winner}; agreement={votes}/{total}; distribution={distribution}",
            answer=winner,
        )
    )
    return Prediction(
        qid=problem.qid,
        answer=winner,
        model=model,
        raw_answer=f"{strategy} winner={winner} agreement={votes}/{total} dist={distribution}",
        strategy=strategy,
        confidence=confidence,
        question_kind=profile.kind,
        prompt_variant=variant,
        attempts=len(answers),
        trace=tuple(steps),
    )


def _solve_self_consistency(
    problem: Problem,
    profile: ProblemProfile,
    client: ChatClient,
    *,
    config: HarnessConfig,
) -> Prediction:
    """Reasoning + self-consistency: sample k reasoned answers, majority-vote, confidence
    = agreement fraction (calibrated, not hard-coded)."""
    answers, trace_steps = _collect_reasoning_votes(
        problem,
        client,
        config.self_consistency_samples,
        config=config,
        label="reasoning_sample",
    )
    return _vote_prediction(
        problem,
        profile,
        client.model,
        answers,
        trace_steps,
        strategy="gemma_self_consistency",
        fallback_reason="invalid_self_consistency",
    )


def _solve_tiered(
    problem: Problem,
    profile: ProblemProfile,
    client: ChatClient,
    *,
    config: HarnessConfig,
    challenger: ChatClient | None = None,
) -> Prediction:
    """Tiered diverse self-consistency, optionally cross-model.

    Tier 1 (cheap): the deterministic anchor plus rotated-choice samples. If every
    tier-1 sample is valid and they agree unanimously, stop — most questions end
    here at a fraction of full-k cost. Otherwise escalate: add seeded temp>0
    rotated samples up to `tiered_total_samples`, plus — when an independent
    challenger model is configured — `challenger_samples` diversified votes from
    it (decorrelated errors), and majority-vote over the whole pool. The primary
    model's votes come first, so first-seen tie-breaking favors the stronger
    multilingual model. Setting tiered_total_samples == tiered_tier1_samples gives
    pure diverse self-consistency with no escalation stage.
    """
    tier1 = config.tiered_tier1_samples
    total = config.tiered_total_samples
    answers, trace_steps = _collect_reasoning_votes(
        problem,
        client,
        tier1,
        config=config,
        label="tier1_sample",
        diversify=True,
    )
    winner, votes, _ = majority_vote(answers)
    unanimous = winner is not None and votes == len(answers)
    escalated = False
    if not unanimous and (total > tier1 or challenger is not None):
        escalated = True
        challenger_note = f"; challenger={challenger.model}" if challenger is not None else ""
        trace_steps.append(
            TraceStep(
                role="synthesizer",
                action="tier_escalation",
                status="warning",
                detail=(
                    f"tier1 agreement={votes}/{len(answers)}; "
                    f"escalating to {total} samples{challenger_note}"
                ),
            )
        )
        if total > tier1:
            more_answers, more_steps = _collect_reasoning_votes(
                problem,
                client,
                total - tier1,
                config=config,
                label="tier2_sample",
                diversify=True,
                start_index=tier1,
            )
            answers = answers + more_answers
            trace_steps = trace_steps + more_steps
        if challenger is not None:
            challenger_answers, challenger_steps = _collect_reasoning_votes(
                problem,
                challenger,
                config.challenger_samples,
                config=config,
                label="challenger_sample",
                diversify=True,
                start_index=total,
            )
            answers = answers + challenger_answers
            trace_steps = trace_steps + challenger_steps
    return _vote_prediction(
        problem,
        profile,
        client.model,
        answers,
        trace_steps,
        strategy="gemma_tiered_escalated" if escalated else "gemma_tiered",
        fallback_reason="invalid_tiered",
    )


def _solve_reading(
    problem: Problem,
    profile: ProblemProfile,
    client: ChatClient,
    *,
    config: HarnessConfig,
) -> Prediction:
    """Passage-grounded reading mode: self-consistency voting where every sample uses
    the reading prompt (quote the passage span, check each option against the text,
    reject true-but-off-topic / wrong-attribution / outside-passage options). Targets
    the ~22% passage bucket, whose failure mode is distractor traps slipping through
    the generic reasoning prompt — not missing knowledge. Reuses the SC sample count
    and token budget; no separate knobs.
    """
    answers, trace_steps = _collect_reasoning_votes(
        problem,
        client,
        config.self_consistency_samples,
        config=config,
        label="reading_sample",
        prompt_builder=build_reading_prompt,
    )
    return _vote_prediction(
        problem,
        profile,
        client.model,
        answers,
        trace_steps,
        strategy="gemma_reading",
        fallback_reason="invalid_reading",
        variant="reading",
    )


def _solve_rag(
    problem: Problem,
    profile: ProblemProfile,
    client: ChatClient,
    *,
    config: HarnessConfig,
) -> Prediction:
    """Targeted retrieval-grounded mode for the legal/admin factual slice.

    BM25 retrieval over a packaged offline corpus feeds reference excerpts into the
    voting loop; the prompt treats them as fallible, so a retrieval miss degrades to
    the model's own knowledge instead of suppressing it. If no corpus is configured,
    nothing is retrieved, or the corpus fails to load, the item degrades to plain
    self-consistency (pred.csv stays complete; the trace records why).
    """
    snippets: tuple = ()
    detail = "no corpus configured"
    if config.rag_corpus_path:
        try:
            retriever = cached_retriever(config.rag_corpus_path)
            query = f"{problem.question} {' '.join(problem.choices)}"
            snippets = tuple(retriever.retrieve(query, config.rag_top_k))
            detail = (
                f"retrieved={','.join(snippet.doc_id for snippet in snippets)}"
                if snippets
                else "no snippets matched"
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            detail = f"retrieval_error={error.__class__.__name__}"
    if not snippets:
        degrade_step = TraceStep(
            role="rag",
            action="retrieve",
            status="warning",
            detail=f"{detail}; degrading to self-consistency",
        )
        return _with_trace(
            _solve_self_consistency(problem, profile, client, config=config),
            (degrade_step,),
        )
    retrieve_step = TraceStep(
        role="rag",
        action="retrieve",
        status="completed",
        detail=detail,
    )
    answers, vote_steps = _collect_reasoning_votes(
        problem,
        client,
        config.self_consistency_samples,
        config=config,
        label="rag_sample",
        prompt_builder=lambda sample_problem, **kwargs: build_rag_prompt(
            sample_problem, snippets, **kwargs
        ),
    )
    return _vote_prediction(
        problem,
        profile,
        client.model,
        answers,
        [retrieve_step, *vote_steps],
        strategy="gemma_rag",
        fallback_reason="invalid_rag",
        variant="rag",
    )


def _is_quantitative(profile: ProblemProfile) -> bool:
    """Route to tool-integrated reasoning only for genuine computation questions."""
    return profile.kind == "calculation" or "has_calculation" in profile.features


def _is_rag_eligible(profile: ProblemProfile, config: HarnessConfig) -> bool:
    """Targeted RAG fires ONLY on the legal/admin factual slice, and only when a
    corpus is configured (default: none, so the router never fires it). The marker
    set is Vietnamese because the packaged corpus is Vietnamese law — a gate matched
    to the corpus, not a language heuristic for answering. The strong (>=2 distinct
    markers) feature is required: single hits are dominated by diacritic-stripped
    polysemy (biology "cơ quan", medical "cấp tính")."""
    return bool(config.rag_corpus_path) and "has_legal_admin_strong" in profile.features


def _is_reading(profile: ProblemProfile) -> bool:
    """Passage questions: the text is supplied, so the lever is grounding, not recall.

    `kind == "reading"` covers the pure case; the feature check additionally catches
    passage questions whose kind was claimed by a higher-priority label (negative,
    many_choice) but which still carry the supplied text.
    """
    return profile.kind == "reading" or "has_long_context" in profile.features


def _solve_tir(
    problem: Problem,
    profile: ProblemProfile,
    client: ChatClient,
    *,
    config: HarnessConfig,
) -> Prediction:
    """Tool-integrated reasoning: the model writes a Python program, we EXECUTE it
    offline, then the model maps the computed result onto an option letter. Voting over
    `tir_samples` independent passes is self-consistency on the SETUP (the failure mode is
    a mis-modeled problem solved deterministically-wrong, not arithmetic slips). Any pass
    that yields no code, no execution, or no valid letter contributes an empty vote; if no
    pass produces a valid answer the item degrades to plain self-consistency reasoning so
    pred.csv stays complete.
    """
    answers: list[str] = []
    trace_steps: list[TraceStep] = []
    for index in range(config.tir_samples):
        sampling: dict[str, float | int] = {}
        if index > 0:
            sampling = {
                "temperature": config.reasoning_temperature,
                "top_p": config.reasoning_top_p,
                "top_k": config.reasoning_top_k,
                "seed": stable_seed(problem.qid, 1000 + index),
            }
        code_prompt = build_tir_code_prompt(problem, max_tokens=config.tir_code_max_tokens)
        raw_code = client.complete(
            code_prompt.system_prompt,
            code_prompt.user_prompt,
            max_tokens=code_prompt.max_tokens,
            **sampling,
        )
        code = extract_code(raw_code)
        if code is None:
            answers.append("")
            trace_steps.append(
                TraceStep(
                    role="tir",
                    action=f"code:{index + 1}",
                    status="warning",
                    detail="model produced no python code block",
                )
            )
            continue
        result = run_python(code, timeout_seconds=config.tir_exec_timeout_seconds)
        trace_steps.append(
            TraceStep(
                role="tir",
                action=f"exec:{index + 1}",
                status="completed" if result.ok else "warning",
                detail=result.summary,
            )
        )
        answer_prompt = build_tir_answer_prompt(
            problem, code, result.stdout or result.stderr
        )
        raw_answer = client.complete(
            answer_prompt.system_prompt,
            answer_prompt.user_prompt,
            max_tokens=answer_prompt.max_tokens,
        )
        normalized = normalize_answer(raw_answer, problem)
        if normalized is None:
            repaired = _repair_invalid_answer(problem, client, raw_answer, config=config)
            normalized = repaired[1] if repaired is not None else None
        answers.append(normalized or "")
        trace_steps.append(
            TraceStep(
                role="tir",
                action=f"answer:{index + 1}",
                status="completed" if normalized else "warning",
                detail="execution-grounded answer" if normalized else "no valid letter",
                answer=normalized,
            )
        )

    if not any(answers):
        trace_steps.append(
            TraceStep(
                role="tir",
                action="degrade",
                status="warning",
                detail="no TIR pass produced a valid letter; falling back to reasoning",
            )
        )
        fallback_answers, fallback_steps = _collect_reasoning_votes(
            problem,
            client,
            config.self_consistency_samples,
            config=config,
            label="tir_fallback_sample",
        )
        return _vote_prediction(
            problem,
            profile,
            client.model,
            fallback_answers,
            trace_steps + fallback_steps,
            strategy="gemma_tir_degraded",
            fallback_reason="invalid_tir",
        )
    return _vote_prediction(
        problem,
        profile,
        client.model,
        answers,
        trace_steps,
        strategy="gemma_tir",
        fallback_reason="invalid_tir",
    )


def _solve_router(
    problem: Problem,
    profile: ProblemProfile,
    client: ChatClient,
    *,
    config: HarnessConfig,
    challenger: ChatClient | None = None,
) -> Prediction:
    """The 'good combination': route each question to the mode that fits its type.

    Quantitative questions (the public test's ~25-30% cross-domain math/physics/chem/
    economics slice, heavy among the 10-choice items) go through tool-integrated
    reasoning — Python execution kills the arithmetic/balance slips that closed-book CoT
    makes. Passage questions (~22%) go through the reading-grounding mode — the text is
    supplied, so quoting the passage and vetting each option against it beats generic
    reasoning. Everything else (civics/history/logic/factual) goes through diverse
    self-consistency, where careful reasoning + voting is the documented lever.
    Quantitative wins over reading when both fire: a calculation stated inside a passage
    still needs the computation done. Reading wins over RAG: when the text is supplied,
    retrieval adds nothing. RAG (legal/admin factual slice) fires only when a corpus is
    configured — default off, so the router is unchanged until measurement turns it on.
    """
    if _is_quantitative(profile):
        return _solve_tir(problem, profile, client, config=config)
    if _is_reading(profile):
        return _solve_reading(problem, profile, client, config=config)
    if _is_rag_eligible(profile, config):
        return _solve_rag(problem, profile, client, config=config)
    return _solve_self_consistency(problem, profile, client, config=config)


def solve_with_challenge(
    problem: Problem,
    client: ChatClient,
    challenger: ChatClient | None,
    *,
    config: HarnessConfig,
) -> Prediction:
    """Tiered, cross-model strategy: run self-consistency with the primary model; if the
    agreement is below the challenge threshold, gather extra reasoned votes from an
    INDEPENDENT challenger model and re-tally over the combined pool. A different model
    breaks the same-model self-confirmation bias, and escalation only fires on uncertain
    items so the time budget is spent where it changes the answer. Degrades to plain
    self-consistency when no challenger is provided.

    Not yet wired into the CLI dispatch: constructing a second provider client needs a
    real model to validate, so the CLI keeps `challenger=None` until then. The logic here
    is fully unit-tested with stub clients.
    """
    profile = classify_problem(problem, config)
    answers, trace_steps = _collect_reasoning_votes(
        problem,
        client,
        config.self_consistency_samples,
        config=config,
        label="reasoning_sample",
    )
    _, votes, total = majority_vote(answers)
    agreement = agreement_confidence(votes, total)

    if challenger is not None and agreement < config.self_consistency_challenge_threshold:
        challenger_answers, challenger_trace = _collect_reasoning_votes(
            problem,
            challenger,
            config.challenger_samples,
            config=config,
            label="challenger_sample",
        )
        trace_steps = trace_steps + [
            TraceStep(
                role="challenger",
                action="cross_model_escalation",
                status="completed",
                detail=(
                    f"primary_agreement={votes}/{total}; "
                    f"threshold={config.self_consistency_challenge_threshold}; "
                    f"challenger={challenger.model}"
                ),
            )
        ] + challenger_trace
        return _vote_prediction(
            problem,
            profile,
            client.model,
            answers + challenger_answers,
            trace_steps,
            strategy="gemma_self_consistency_challenged",
            fallback_reason="invalid_self_consistency_challenged",
        )

    return _vote_prediction(
        problem,
        profile,
        client.model,
        answers,
        trace_steps,
        strategy="gemma_self_consistency",
        fallback_reason="invalid_self_consistency",
    )


def _break_tie(
    problem: Problem,
    client: ChatClient,
    tied_answers: tuple[str, ...],
) -> tuple[str, str | None]:
    prompt = build_tiebreak_prompt(problem, tied_answers)
    raw_tiebreak = client.complete(
        prompt.system_prompt,
        prompt.user_prompt,
        max_tokens=prompt.max_tokens,
    )
    return raw_tiebreak, normalize_answer(raw_tiebreak, problem)


def _verify(
    problem: Problem,
    client: ChatClient,
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
    client: ChatClient,
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
    if profile.features:
        detail = f"{detail}; features={','.join(profile.features)}"
    if profile.diagnostics:
        detail = f"{detail}; diagnostics={','.join(profile.diagnostics)}"
    return TraceStep(
        role="classifier",
        action="profile_problem",
        status="completed",
        detail=detail,
    )


def _with_trace(prediction: Prediction, prefix: tuple[TraceStep, ...]) -> Prediction:
    return replace(prediction, trace=prefix + prediction.trace)
