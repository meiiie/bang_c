"""Answer extraction robustness for real chain-of-thought output.

The reasoning prompt asks the model to end with `ANSWER: <letter>`, but models often
phrase the conclusion naturally ("the answer is A", "Answer: (C)"). normalize_answer must
extract the letter from these without ever picking up a bare article letter from prose.
All deterministic — no model required.
"""

from __future__ import annotations

import unittest

from hackaithon_c.normalize import normalize_answer
from hackaithon_c.schema import Problem


def _problem() -> Problem:
    return Problem(qid="n", question="Which option?", choices=("alpha", "beta", "gamma", "delta"))


class NormalizeCoTTests(unittest.TestCase):
    def test_extracts_from_natural_cot_endings(self) -> None:
        problem = _problem()
        cases = {
            "ANSWER: A": "A",
            "The answer is A.": "A",
            "answer is b": "B",
            "Answer: (C)": "C",
            "**ANSWER: D**": "D",
            "Reasoning eliminates others. Final: C": "C",
            "Let me think... ANSWER: B": "B",
        }
        for text, expected in cases.items():
            self.assertEqual(normalize_answer(text, problem), expected, msg=repr(text))

    def test_does_not_extract_article_letter_from_prose(self) -> None:
        # Pinned behaviour: no answer-indicator word -> no extraction (the article "a").
        problem = _problem()
        self.assertIsNone(
            normalize_answer("The question asks for a crime in the context.", problem)
        )

    def test_still_prefers_last_visible_valid_letter(self) -> None:
        problem = _problem()
        self.assertEqual(normalize_answer("Reasoning says A. Final: C", problem), "C")

    def test_invalid_letter_outside_choices_is_rejected(self) -> None:
        problem = _problem()  # only A-D valid
        self.assertIsNone(normalize_answer("ANSWER: Z", problem))


if __name__ == "__main__":
    unittest.main()
