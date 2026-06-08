from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from hackaithon_c.exporter import write_predictions
from hackaithon_c.loader import load_problems
from hackaithon_c.schema import Prediction


class ContestContractTest(unittest.TestCase):
    def test_json_loader_supports_public_test_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0001",
                            "question": "Cau hoi mau?",
                            "choices": ["Mot", "Hai", "Ba", "Bon"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            problems = load_problems(path)

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].qid, "test_0001")
        self.assertEqual(problems[0].allowed_letters, "ABCD")

    def test_csv_export_uses_exact_submission_columns(self) -> None:
        prediction = Prediction(
            qid="test_0001",
            answer="C",
            model="heuristic",
            raw_answer="C",
            strategy="test",
            confidence=1.0,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pred.csv"
            write_predictions(path, [prediction])
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows, [{"qid": "test_0001", "answer": "C"}])


if __name__ == "__main__":
    unittest.main()
