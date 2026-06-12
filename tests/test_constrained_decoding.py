"""Constrained decoding on the repair pass.

When a chain-of-thought sample produces no parseable letter, the repair re-ask is
issued with `letters=<valid options>`. The local llama.cpp runtime turns that into a
GBNF grammar that admits exactly one option letter, so a free-text drift can never
fall through to the heuristic fallback (accuracy AND pred.csv contract robustness).

These are stub-level tests: they pin the contract (repair requests constrained
decoding; the grammar builder degrades gracefully without llama-cpp) without needing a
GPU. The grammar's runtime effect is validated at the image smoke test.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from hackaithon_c.config import load_config
from hackaithon_c.local_client import _letter_grammar
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


class LetterCapturingClient:
    model = "stub/gemma-4"

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.letters_seen: list[str | None] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, letters=None, **_kw) -> str:
        self.letters_seen.append(letters)
        return self.answers.pop(0)


def _problem() -> Problem:
    return Problem(qid="c1", question="Pick one.", choices=("alpha", "beta", "gamma", "delta"))


class LetterGrammarUnit(unittest.TestCase):
    def test_none_and_empty_return_none(self) -> None:
        self.assertIsNone(_letter_grammar(None))
        self.assertIsNone(_letter_grammar(""))

    def test_no_valid_letters_returns_none(self) -> None:
        self.assertIsNone(_letter_grammar("123!"))

    def test_valid_letters_never_raise(self) -> None:
        # Returns a grammar when llama-cpp is present, None when it is not (test env).
        # Either way it must not raise — the run can never be broken by grammar build.
        try:
            _letter_grammar("ABCD")
        except Exception as exc:  # pragma: no cover - guards the defensive contract
            self.fail(f"_letter_grammar must never raise, got {exc!r}")


class RepairRequestsConstrainedDecoding(unittest.TestCase):
    def test_repair_pass_sends_letters(self) -> None:
        # Sample 0 has no letter -> a repair call must follow, carrying the option
        # letters so the local runtime can constrain the output.
        client = LetterCapturingClient(["rambling with no answer line", "B"])
        pred = solve_problem(
            _problem(),
            client,
            strategy="self_consistency",
            config=_config(self_consistency_samples=1),
        )
        self.assertEqual(pred.answer, "B")
        self.assertIn("ABCD", [s for s in client.letters_seen if s])

    def test_clean_answer_does_not_trigger_repair(self) -> None:
        client = LetterCapturingClient(["ANSWER: C"])
        solve_problem(
            _problem(),
            client,
            strategy="self_consistency",
            config=_config(self_consistency_samples=1),
        )
        # Only the reasoning call (letters=None); no constrained repair was needed.
        self.assertEqual(client.letters_seen, [None])


if __name__ == "__main__":
    unittest.main()
