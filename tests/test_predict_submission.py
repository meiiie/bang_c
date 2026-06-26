"""Contract tests for predict.py (the BTC Round-2 submission entry point).

Runs predict.py in dry-run (no model/GPU) and asserts it emits the two BTC
artifacts with the exact required shape:
    submission.csv        -> qid,answer
    submission_time.csv   -> qid,answer,time
Every qid is covered, in input order, with a per-row-valid letter and a numeric
time. NEKO_OUTPUT_DIR keeps the run isolated to a temp dir.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PREDICT = REPO_ROOT / "predict.py"


class PredictSubmissionContractTest(unittest.TestCase):
    def _run(self, items: list[dict]) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "private_test.json").write_text(
            json.dumps(items, ensure_ascii=False), encoding="utf-8"
        )
        out = tmp / "out"
        out.mkdir()
        env = dict(os.environ)
        env["NEKO_DRY_RUN"] = "1"
        env["NEKO_OUTPUT_DIR"] = str(out)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(PREDICT), str(tmp / "private_test.json")],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        return out

    def test_writes_both_btc_artifacts_in_order(self) -> None:
        items = [
            {"qid": "test_0001", "question": "2+2=?", "choices": ["3", "4", "5", "6"]},
            {"qid": "test_0002", "question": "Thu do VN?", "choices": ["Ha Noi", "Hue", "Da Nang"]},
            {"qid": "test_0003", "question": "Q3", "choices": ["a", "b", "c", "d"]},
        ]
        out = self._run(items)
        submission = out / "submission.csv"
        timing = out / "submission_time.csv"
        self.assertTrue(submission.is_file())
        self.assertTrue(timing.is_file())

        with submission.open(encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0], ["qid", "answer"])
        self.assertEqual([r[0] for r in rows[1:]], ["test_0001", "test_0002", "test_0003"])
        for row in rows[1:]:
            self.assertTrue(row[1] and row[1].isalpha(), msg=f"bad answer row: {row}")

        with timing.open(encoding="utf-8") as handle:
            trows = list(csv.reader(handle))
        self.assertEqual(trows[0], ["qid", "answer", "time"])
        self.assertEqual(len(trows), 4)  # header + 3
        for row in trows[1:]:
            float(row[2])  # numeric time or raises

    def test_answer_letter_in_range_per_row(self) -> None:
        # A 3-choice question must never produce 'D'.
        out = self._run([{"qid": "test_0001", "question": "Q", "choices": ["x", "y", "z"]}])
        with (out / "submission.csv").open(encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        self.assertIn(rows[1][1], {"A", "B", "C"})


if __name__ == "__main__":
    unittest.main()
