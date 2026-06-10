"""P1 — reasoning + self-consistency + agreement-based calibration.

Deterministic tests using a scripted stub client (no real model needed). They verify the
voting logic, the calibrated confidence, chain-of-thought letter extraction, the
language-neutral reasoning prompt, and graceful fallback when no sample yields a letter.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from hackaithon_c.calibration import (
    agreement_confidence,
    majority_vote,
    vote_distribution,
)
from hackaithon_c.config import load_config
from hackaithon_c.prompting import build_reasoning_prompt
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem, solve_with_challenge


class ScriptedClient:
    model = "stub/gemma-4"

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 12) -> str:
        self.calls += 1
        return self.answers.pop(0)


def _problem() -> Problem:
    return Problem(
        qid="t1",
        question="Which option is correct?",
        choices=("alpha", "beta", "gamma", "delta"),
    )


def _config_with_samples(n: int):
    """Production default is k=1; the multi-sample voting mechanism is tested with an
    explicit k>=2 config so split-vote / escalation scenarios are meaningful."""
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {})["self_consistency_samples"] = n
    return replace(base, raw=raw)


class CalibrationTests(unittest.TestCase):
    def test_majority_vote_unanimous(self) -> None:
        self.assertEqual(majority_vote(["A", "A", "A"]), ("A", 3, 3))

    def test_majority_vote_plurality(self) -> None:
        self.assertEqual(majority_vote(["A", "A", "B"]), ("A", 2, 3))

    def test_majority_vote_tie_breaks_by_first_seen_not_alphabet(self) -> None:
        # B and A both have 2 votes; B appears first -> B wins (no 'A' bias).
        self.assertEqual(majority_vote(["B", "A", "B", "A"]), ("B", 2, 4))

    def test_majority_vote_ignores_empty_and_handles_none(self) -> None:
        self.assertEqual(majority_vote(["", "C", ""]), ("C", 1, 1))
        self.assertEqual(majority_vote(["", "", ""]), (None, 0, 0))

    def test_agreement_confidence(self) -> None:
        self.assertEqual(agreement_confidence(3, 3), 1.0)
        self.assertAlmostEqual(agreement_confidence(2, 3), 2 / 3)
        self.assertEqual(agreement_confidence(0, 0), 0.0)

    def test_vote_distribution_sorted(self) -> None:
        self.assertEqual(vote_distribution(["B", "A", "B", ""]), "A:1,B:2")


class ReasoningPromptTests(unittest.TestCase):
    def test_prompt_is_language_neutral_and_allows_reasoning(self) -> None:
        bundle = build_reasoning_prompt(_problem(), max_tokens=512)
        system = bundle.system_prompt.lower()
        self.assertNotIn("vietnamese multiple-choice", system)
        self.assertIn("any language", system)
        self.assertIn("step by step", system)
        self.assertIn("answer:", system)
        self.assertEqual(bundle.max_tokens, 512)


class SelfConsistencySolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _config_with_samples(5)
        self.k = self.config.self_consistency_samples

    def test_production_default_is_single_cot(self) -> None:
        # The shipped contest default is k=1 (validated on the real model; 87.26 leaderboard).
        self.assertEqual(load_config().self_consistency_samples, 1)

    def test_unanimous_gives_full_confidence(self) -> None:
        client = ScriptedClient(["ANSWER: A"] * self.k)
        pred = solve_problem(_problem(), client, strategy="self_consistency", config=self.config)
        self.assertEqual(pred.answer, "A")
        self.assertEqual(pred.confidence, 1.0)
        self.assertEqual(pred.strategy, "gemma_self_consistency")
        self.assertEqual(pred.attempts, self.k)
        self.assertEqual(client.calls, self.k)

    def test_split_vote_yields_calibrated_confidence(self) -> None:
        # k samples: ceil(k/2) say A, the rest say B -> winner A with real agreement < 1.
        a_count = self.k // 2 + 1
        scripted = ["ANSWER: A"] * a_count + ["ANSWER: B"] * (self.k - a_count)
        client = ScriptedClient(scripted)
        pred = solve_problem(_problem(), client, strategy="self_consistency", config=self.config)
        self.assertEqual(pred.answer, "A")
        self.assertAlmostEqual(pred.confidence, a_count / self.k)
        self.assertLess(pred.confidence, 1.0)

    def test_extracts_letter_from_chain_of_thought(self) -> None:
        cot = (
            "Let me reason. Alpha is wrong, gamma is wrong, beta fits best.\n"
            "Therefore the answer is B.\nANSWER: B"
        )
        client = ScriptedClient([cot] * self.k)
        pred = solve_problem(_problem(), client, strategy="self_consistency", config=self.config)
        self.assertEqual(pred.answer, "B")
        self.assertEqual(pred.confidence, 1.0)

    def test_all_invalid_falls_back_to_valid_letter(self) -> None:
        client = ScriptedClient(["I cannot decide."] * self.k)
        pred = solve_problem(_problem(), client, strategy="self_consistency", config=self.config)
        self.assertIn(pred.answer, _problem().allowed_letters)
        self.assertIn("self_consistency", pred.fallback_reason or "")


class CrossModelChallengeTests(unittest.TestCase):
    """P3 — escalate to an independent challenger model only when primary agreement is low."""

    def setUp(self) -> None:
        self.config = _config_with_samples(5)
        self.k = self.config.self_consistency_samples

    def _split(self, top: int, other: int) -> list[str]:
        return ["ANSWER: A"] * top + ["ANSWER: B"] * other

    def test_high_agreement_does_not_consult_challenger(self) -> None:
        primary = ScriptedClient(["ANSWER: A"] * self.k)
        challenger = ScriptedClient(["ANSWER: B"] * self.config.challenger_samples)
        pred = solve_with_challenge(_problem(), primary, challenger, config=self.config)
        self.assertEqual(pred.answer, "A")
        self.assertEqual(pred.confidence, 1.0)
        self.assertEqual(pred.strategy, "gemma_self_consistency")
        self.assertEqual(challenger.calls, 0)

    def test_low_agreement_escalates_and_challenger_confirms(self) -> None:
        a = self.k // 2 + 1  # bare majority -> agreement < threshold 0.75
        primary = ScriptedClient(self._split(a, self.k - a))
        challenger = ScriptedClient(["ANSWER: A"] * self.config.challenger_samples)
        pred = solve_with_challenge(_problem(), primary, challenger, config=self.config)
        self.assertEqual(pred.answer, "A")
        self.assertEqual(pred.strategy, "gemma_self_consistency_challenged")
        self.assertEqual(challenger.calls, self.config.challenger_samples)
        self.assertEqual(pred.attempts, self.k + self.config.challenger_samples)

    def test_low_agreement_challenger_can_flip_answer(self) -> None:
        a = self.k // 2 + 1
        primary = ScriptedClient(self._split(a, self.k - a))  # narrow A majority
        challenger = ScriptedClient(["ANSWER: B"] * self.config.challenger_samples)
        pred = solve_with_challenge(_problem(), primary, challenger, config=self.config)
        # combined pool now favours B (a A vs (k-a)+challenger B)
        self.assertEqual(pred.answer, "B")
        self.assertEqual(pred.strategy, "gemma_self_consistency_challenged")

    def test_no_challenger_degrades_to_self_consistency(self) -> None:
        a = self.k // 2 + 1
        primary = ScriptedClient(self._split(a, self.k - a))
        pred = solve_with_challenge(_problem(), primary, None, config=self.config)
        self.assertEqual(pred.answer, "A")
        self.assertEqual(pred.strategy, "gemma_self_consistency")
        self.assertAlmostEqual(pred.confidence, a / self.k)


if __name__ == "__main__":
    unittest.main()
