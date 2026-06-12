"""Bulletproof pred.csv contract.

A contest submission scores on /output/pred.csv. The single worst failure mode is
an absent or partial file, which scores zero. These tests pin the two guarantees:

1. `repair_predictions_for_contract` always yields exactly the input qids, in input
   order, each with a letter valid for its own problem -- good predictions verbatim,
   gaps/out-of-range/dupes replaced by a deterministic fallback.
2. A solver that raises on some questions never prevents pred.csv from being written,
   and the written file covers every input qid with a valid letter.
"""

from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hackaithon_c.config import load_config
from hackaithon_c.evaluation import (
    repair_predictions_for_contract,
    validate_predictions,
)
from hackaithon_c.run import main
from hackaithon_c.schema import Prediction, Problem


def _pred(qid: str, answer: str, **kw) -> Prediction:
    base = dict(model="stub/gemma-4", raw_answer=answer, strategy="self_consistency", confidence=0.9)
    base.update(kw)
    return Prediction(qid=qid, answer=answer, **base)


def _problem(qid: str, n_choices: int = 4) -> Problem:
    return Problem(qid=qid, question=f"Q {qid}", choices=tuple(f"opt{i}" for i in range(n_choices)))


class RepairUnit(unittest.TestCase):
    def test_keeps_good_predictions_verbatim(self) -> None:
        problems = [_problem("a"), _problem("b")]
        preds = [_pred("a", "C"), _pred("b", "A")]
        repaired = repair_predictions_for_contract(problems, preds)
        self.assertEqual([(p.qid, p.answer) for p in repaired], [("a", "C"), ("b", "A")])
        # Same objects -> accuracy never altered.
        self.assertIs(repaired[0], preds[0])

    def test_fills_missing_qid(self) -> None:
        problems = [_problem("a"), _problem("b"), _problem("c")]
        repaired = repair_predictions_for_contract(problems, [_pred("a", "B")])
        self.assertEqual([p.qid for p in repaired], ["a", "b", "c"])
        for p, prob in zip(repaired, problems):
            self.assertIn(p.answer, prob.allowed_letters)
        self.assertEqual(repaired[1].fallback_reason, "contract_repair")

    def test_replaces_out_of_range_letter(self) -> None:
        # 'Z' is not valid for a 4-choice problem; must be repaired to a valid letter.
        problems = [_problem("a", n_choices=4)]
        repaired = repair_predictions_for_contract(problems, [_pred("a", "Z")])
        self.assertIn(repaired[0].answer, "ABCD")

    def test_drops_duplicate_and_extra(self) -> None:
        problems = [_problem("a")]
        preds = [_pred("a", "B"), _pred("a", "D"), _pred("ghost", "A")]
        repaired = repair_predictions_for_contract(problems, preds)
        self.assertEqual([p.qid for p in repaired], ["a"])
        self.assertEqual(repaired[0].answer, "B")  # first occurrence wins

    def test_repaired_list_passes_validation(self) -> None:
        problems = [_problem("a"), _problem("b", n_choices=10)]
        repaired = repair_predictions_for_contract(problems, [])
        summary = validate_predictions(problems, repaired, load_config())
        self.assertTrue(summary.valid, summary.issues)


class WriteBeforeRaiseIntegration(unittest.TestCase):
    def test_pred_csv_written_even_when_solver_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            (data / "public_test.json").write_text(
                '[{"qid":"q1","question":"pick","choices":["a","b","c","d"]},'
                '{"qid":"q2","question":"pick","choices":["a","b","c","d"]}]',
                encoding="utf-8",
            )
            out = root / "out"
            # dry_run uses the heuristic (no model), so this exercises the full
            # load -> solve -> repair -> write path without a GPU and never raises.
            code = main(
                (
                    "--input", str(data / "public_test.json"),
                    "--output-dir", str(out),
                    "--dry-run",
                    "--strategy", "self_consistency",
                )
            )
            self.assertEqual(code, 0)
            pred = out / load_config().output_file
            self.assertTrue(pred.exists(), "pred.csv must always be written")
            rows = list(csv.DictReader(pred.open(encoding="utf-8")))
            self.assertEqual([r["qid"] for r in rows], ["q1", "q2"])
            for r in rows:
                self.assertIn(r["answer"], "ABCD")


if __name__ == "__main__":
    unittest.main()
