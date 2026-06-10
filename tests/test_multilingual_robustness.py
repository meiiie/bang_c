"""Phase 0 safety net.

These tests assert that the harness can *load, classify, and dry-run-solve* a
hand-authored, multilingual (VI/EN/KO/ZH) gold set without crashing or producing an
invalid answer letter. The fixture is our own authored Q&A — not contest data — used as
a regression set (see notes/EXECUTOR-PLAYBOOK.md Sec. 6).

They intentionally do NOT assert routing correctness or accuracy: the diacritic /
keyword-routing bugs and the no-reasoning constraint are fixed in later phases. Phase 0
only guarantees the pipeline is *robust* to non-Vietnamese and CJK input, which the
overfit/multilingual audit flagged as a silent no-op surface today.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from hackaithon_c.classifier import classify_problem
from hackaithon_c.config import load_config
from hackaithon_c.loader import load_problems
from hackaithon_c.schema import Problem, QuestionKind
from hackaithon_c.solver import solve_problem


_GOLD_PATH = Path(__file__).parent / "fixtures" / "multilingual_gold.json"
_VALID_KINDS = set(QuestionKind.__args__)


def _gold_rows() -> list[dict]:
    return json.loads(_GOLD_PATH.read_text(encoding="utf-8"))


class MultilingualGoldFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()
        self.problems = load_problems(_GOLD_PATH)
        self.rows = _gold_rows()

    def test_fixture_loads_every_row(self) -> None:
        self.assertEqual(len(self.problems), len(self.rows))
        self.assertGreaterEqual(len(self.problems), 15)
        for problem in self.problems:
            self.assertTrue(problem.qid)
            self.assertTrue(problem.question)
            self.assertGreaterEqual(len(problem.choices), 2)

    def test_authored_answers_are_valid_letters(self) -> None:
        """Sanity check on our own fixture: each gold answer is a real choice letter."""
        by_qid = {p.qid: p for p in self.problems}
        for row in self.rows:
            problem = by_qid[row["qid"]]
            self.assertIn(
                row["answer"],
                problem.allowed_letters,
                msg=f"{row['qid']}: answer {row['answer']} not in {problem.allowed_letters}",
            )

    def test_every_item_classifies_without_error(self) -> None:
        for problem in self.problems:
            profile = classify_problem(problem, self.config)
            self.assertIn(profile.kind, _VALID_KINDS, msg=f"{problem.qid}: bad kind {profile.kind}")
            self.assertTrue(profile.prompt_variant, msg=f"{problem.qid}: empty prompt_variant")
            self.assertEqual(len(problem.allowed_letters), len(problem.choices))

    def test_dry_run_solve_returns_valid_letter_for_all(self) -> None:
        for problem in self.problems:
            prediction = solve_problem(problem, None, dry_run=True, config=self.config)
            self.assertIn(
                prediction.answer,
                problem.allowed_letters,
                msg=f"{problem.qid}: dry-run answer {prediction.answer!r} invalid",
            )

    def test_cjk_items_do_not_crash_the_heuristic_layer(self) -> None:
        """KO/ZH text exercises the [a-z0-9]/diacritic-blind heuristics; must not crash."""
        cjk_qids = {row["qid"] for row in self.rows if row["lang"] in {"ko", "zh"}}
        self.assertGreaterEqual(len(cjk_qids), 4)
        for problem in self.problems:
            if problem.qid not in cjk_qids:
                continue
            profile = classify_problem(problem, self.config)
            self.assertIn(profile.kind, _VALID_KINDS)
            prediction = solve_problem(problem, None, dry_run=True, config=self.config)
            self.assertIn(prediction.answer, problem.allowed_letters)


class CalculationRoutingTests(unittest.TestCase):
    """Calculation routing must require a *real* computation signal, not a topic word
    ("formula"/"value") plus an incidental digit sitting in the answer choices."""

    def setUp(self) -> None:
        self.config = load_config()

    def _kind(self, question: str, choices: tuple[str, ...]) -> str:
        return classify_problem(Problem(qid="rt", question=question, choices=choices), self.config).kind

    def test_topic_word_with_only_choice_digits_is_not_calculation(self) -> None:
        # "formula" + digits only inside the choices (CO2/H2O) must NOT route calculation.
        self.assertNotEqual(
            self._kind("What is the chemical formula for water?", ("CO2", "H2O", "O2", "NaCl")),
            "calculation",
        )
        self.assertNotEqual(
            self._kind("Giá trị tư tưởng của tác phẩm này là gì?", ("Nhân đạo", "Hiện thực", "Cả hai", "Khác")),
            "calculation",
        )

    def test_real_arithmetic_still_routes_calculation(self) -> None:
        self.assertEqual(self._kind("Tính 2 + 2 bằng bao nhiêu?", ("3", "4", "5", "6")), "calculation")
        self.assertEqual(self._kind("What is 15 percent of 200?", ("15", "20", "30", "45")), "calculation")
        self.assertEqual(self._kind("Một sản phẩm giá 500.000đ giảm 20%, còn bao nhiêu?", ("400.000", "450.000", "480.000", "300.000")), "calculation")


class NegationRoutingTests(unittest.TestCase):
    """Multilingual negation must route to the negative/elimination profile so 'choose the
    FALSE one' questions are handled across languages (config-driven cues, not code)."""

    def setUp(self) -> None:
        self.config = load_config()
        self.problems = {p.qid: p for p in load_problems(_GOLD_PATH)}

    def _kind(self, qid: str) -> str:
        return classify_problem(self.problems[qid], self.config).kind

    def test_negation_detected_across_languages(self) -> None:
        for qid in ("gold_vi_neg_01", "gold_en_neg_01", "gold_ko_neg_01", "gold_zh_neg_01", "gold_fr_neg_01"):
            self.assertEqual(self._kind(qid), "negative", msg=f"{qid} should route negative")

    def test_structural_routing_is_language_agnostic(self) -> None:
        # French "combien ... 7 ... 6" -> calculation; Korean 6-option item -> many_choice.
        self.assertEqual(self._kind("gold_fr_math_01"), "calculation")
        self.assertEqual(self._kind("gold_ko_manychoice_01"), "many_choice")


if __name__ == "__main__":
    unittest.main()
