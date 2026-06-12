"""Tiered diverse self-consistency + position-bias debiasing (the 93+ push levers).

Deterministic stub tests — no model needed. They verify: rotation math and letter
mapping back to the original space; that a position-biased model (always answers
"A") is caught by the rotated sample and triggers escalation; that a content-
consistent model stops early at tier 1; that diversified samples carry seeded
temperature>0 sampling parameters; and the challenger-client builder gating.
"""

from __future__ import annotations

import copy
import re
import unittest
from dataclasses import replace

from hackaithon_c.config import load_config
from hackaithon_c.model_client import build_challenger_client
from hackaithon_c.permute import (
    original_letter,
    rotate_problem,
    rotation_for_sample,
    stable_seed,
)
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem


def _problem() -> Problem:
    return Problem(
        qid="t1",
        question="Which option is correct?",
        choices=("alpha", "beta", "gamma", "delta"),
    )


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


class PositionBiasedClient:
    """Always answers the FIRST option — the classic position bias."""

    model = "stub/biased"

    def __init__(self) -> None:
        self.calls = 0
        self.sampling: list[dict] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, temperature=None, top_p=None, top_k=None, seed=None, letters=None):
        self.calls += 1
        self.sampling.append({"temperature": temperature, "top_p": top_p, "top_k": top_k, "seed": seed})
        return "ANSWER: A"


class ContentAwareClient:
    """Answers whichever letter currently holds the target choice text — i.e. a
    model whose answer is robust to choice order."""

    model = "stub/consistent"

    def __init__(self, target_text: str) -> None:
        self.target = target_text
        self.calls = 0
        self.sampling: list[dict] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, temperature=None, top_p=None, top_k=None, seed=None, letters=None):
        self.calls += 1
        self.sampling.append({"temperature": temperature, "top_p": top_p, "top_k": top_k, "seed": seed})
        for line in user_prompt.splitlines():
            match = re.match(r"^([A-Z])\.\s+(.*)$", line.strip())
            if match and self.target in match.group(2):
                return f"ANSWER: {match.group(1)}"
        return "ANSWER: A"


class PermuteTests(unittest.TestCase):
    def test_sample_zero_is_identity(self) -> None:
        self.assertEqual(rotation_for_sample(0, 4), 0)

    def test_rotations_cycle_through_non_identity(self) -> None:
        rotations = [rotation_for_sample(i, 4) for i in range(1, 7)]
        self.assertEqual(rotations, [1, 2, 3, 1, 2, 3])

    def test_two_choice_and_degenerate_problems_are_safe(self) -> None:
        self.assertEqual(rotation_for_sample(3, 2), 1)
        self.assertEqual(rotation_for_sample(3, 1), 0)

    def test_rotate_problem_reorders_choices(self) -> None:
        rotated = rotate_problem(_problem(), 1)
        self.assertEqual(rotated.choices, ("beta", "gamma", "delta", "alpha"))
        self.assertEqual(rotated.qid, "t1")

    def test_original_letter_round_trip(self) -> None:
        problem = _problem()
        for rotation in range(4):
            rotated = rotate_problem(problem, rotation)
            for original_index, text in enumerate(problem.choices):
                rotated_index = rotated.choices.index(text)
                rotated_letter = problem.allowed_letters[rotated_index]
                self.assertEqual(
                    original_letter(rotated_letter, rotation, problem),
                    problem.allowed_letters[original_index],
                    msg=f"rotation={rotation} text={text}",
                )

    def test_original_letter_rejects_invalid(self) -> None:
        self.assertIsNone(original_letter("Z", 1, _problem()))

    def test_stable_seed_is_deterministic_and_distinct(self) -> None:
        self.assertEqual(stable_seed("q1", 1), stable_seed("q1", 1))
        self.assertNotEqual(stable_seed("q1", 1), stable_seed("q1", 2))
        self.assertNotEqual(stable_seed("q1", 1), stable_seed("q2", 1))


class TieredStrategyTests(unittest.TestCase):
    def test_consistent_model_stops_at_tier1(self) -> None:
        # Content-robust model: anchor says B; rotated sample maps back to B too.
        client = ContentAwareClient("beta")
        pred = solve_problem(_problem(), client, strategy="tiered", config=_config())
        self.assertEqual(pred.answer, "B")
        self.assertEqual(pred.strategy, "gemma_tiered")
        self.assertEqual(pred.confidence, 1.0)
        self.assertEqual(client.calls, 2)  # tier 1 only — the cheap path

    def test_position_biased_model_triggers_escalation(self) -> None:
        # Always-"A" model: anchor=A but the rotated sample maps back to B -> disagree
        # -> escalate to 5 samples. Votes: A,B + (rot 2,3,1 -> C,D,B) => B wins 2/5.
        client = PositionBiasedClient()
        pred = solve_problem(_problem(), client, strategy="tiered", config=_config())
        self.assertEqual(pred.strategy, "gemma_tiered_escalated")
        self.assertEqual(client.calls, 5)
        self.assertEqual(pred.answer, "B")
        self.assertAlmostEqual(pred.confidence, 2 / 5)

    def test_diversified_samples_use_seeded_temperature(self) -> None:
        client = PositionBiasedClient()
        solve_problem(_problem(), client, strategy="tiered", config=_config())
        anchor = client.sampling[0]
        self.assertIsNone(anchor["temperature"])  # deterministic anchor untouched
        for index, sampling in enumerate(client.sampling[1:], start=1):
            self.assertEqual(sampling["temperature"], 0.8, msg=f"sample {index}")
            self.assertEqual(sampling["top_p"], 0.95, msg=f"sample {index}")
            self.assertEqual(sampling["top_k"], 64, msg=f"sample {index}")
            self.assertEqual(sampling["seed"], stable_seed("t1", index), msg=f"sample {index}")

    def test_equal_tier_sizes_means_pure_diverse_self_consistency(self) -> None:
        config = _config(tiered_tier1_samples=3, tiered_total_samples=3)
        client = PositionBiasedClient()
        pred = solve_problem(_problem(), client, strategy="tiered", config=config)
        self.assertEqual(client.calls, 3)  # no escalation stage exists
        self.assertEqual(pred.strategy, "gemma_tiered")


class CrossModelTieredTests(unittest.TestCase):
    """When a challenger is configured, the tiered escalation pools its votes."""

    def test_tier1_agreement_never_consults_challenger(self) -> None:
        primary = ContentAwareClient("beta")
        challenger = ContentAwareClient("gamma")
        pred = solve_problem(
            _problem(), primary, strategy="tiered", config=_config(), challenger=challenger
        )
        self.assertEqual(pred.answer, "B")
        self.assertEqual(pred.strategy, "gemma_tiered")
        self.assertEqual(challenger.calls, 0)

    def test_escalation_pools_challenger_votes(self) -> None:
        # Position-biased primary disagrees at tier 1 -> escalate. Primary's 5 votes
        # scatter (A,B,C,D,B); a content-robust challenger adds 3 unanimous "C" votes
        # (mapped back through its rotations) -> pooled C:4 of 8 wins.
        primary = PositionBiasedClient()
        challenger = ContentAwareClient("gamma")
        pred = solve_problem(
            _problem(), primary, strategy="tiered", config=_config(), challenger=challenger
        )
        self.assertEqual(pred.strategy, "gemma_tiered_escalated")
        self.assertEqual(primary.calls, 5)
        self.assertEqual(challenger.calls, 3)  # config challenger_samples default
        self.assertEqual(pred.answer, "C")
        self.assertAlmostEqual(pred.confidence, 4 / 8)

    def test_no_challenger_keeps_prior_behavior(self) -> None:
        primary = PositionBiasedClient()
        pred = solve_problem(_problem(), primary, strategy="tiered", config=_config())
        self.assertEqual(pred.answer, "B")
        self.assertEqual(primary.calls, 5)


class ChallengerBuilderTests(unittest.TestCase):
    def test_unconfigured_returns_none(self) -> None:
        self.assertIsNone(build_challenger_client(load_config()))

    def test_local_challenger_is_built_lazily(self) -> None:
        config = _config(
            challenger_provider="local_llamacpp",
            challenger_model_path="/models/qwen3.5-8b.gguf",
            challenger_model_id="qwen/qwen3.5-8b-q4",
        )
        client = build_challenger_client(config)
        self.assertIsNotNone(client)
        self.assertEqual(client.model, "qwen/qwen3.5-8b-q4")  # no model load at build

    def test_unsupported_provider_is_rejected(self) -> None:
        config = _config(
            challenger_provider="nvidia",
            challenger_model_path="x",
        )
        with self.assertRaises(ValueError):
            build_challenger_client(config)


if __name__ == "__main__":
    unittest.main()
