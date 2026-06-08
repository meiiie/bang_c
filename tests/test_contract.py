from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from hackaithon_c.branding import ascii_logo, version_line
from hackaithon_c.capabilities import collect_capabilities, render_capabilities
from hackaithon_c.classifier import classify_problem
from hackaithon_c.config import load_config
from hackaithon_c.doctor import collect_doctor_checks, render_doctor_report
from hackaithon_c.evaluation import validate_predictions
from hackaithon_c.exporter import write_predictions
from hackaithon_c.loader import load_problems
from hackaithon_c.normalize import normalize_answer
from hackaithon_c.prompting import build_prompt
from hackaithon_c.schema import Prediction
from hackaithon_c.solver import solve_problem
from hackaithon_c.workflows import list_workflows, render_workflows, resolve_workflow


class FakeClient:
    model = "fake/gemma-4"

    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 12) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return self.answers.pop(0)


class ContestContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()

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

    def test_classifier_selects_many_choice_tournament_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0002",
                            "question": "Chon dap an dung nhat.",
                            "choices": [f"Lua chon {index}" for index in range(10)],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "many_choice")
        self.assertTrue(profile.should_tournament)
        self.assertEqual(build_prompt(problem, profile, config=self.config).variant, "elimination")

    def test_classifier_handles_translated_negative_question(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "private_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "private_0001",
                            "question": "Texto: La capital es Paris.\nPregunta: Cual opcion no es correcta?",
                            "choices": ["Paris es capital", "Berlin es capital", "Francia esta en Europa", "Paris esta en Francia"],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "negative")
        self.assertEqual(profile.prompt_variant, "elimination")

    def test_default_config_has_expected_contract_shape(self) -> None:
        self.assertEqual(self.config.brand_name, "Neko Core")
        self.assertEqual(self.config.output_columns, ("qid", "answer"))
        self.assertIn("private_test.csv", self.config.input_candidates)
        self.assertGreater(self.config.rubric["contract"], 0)
        self.assertTrue(ascii_logo(self.config))
        self.assertIn("Neko Core", version_line(self.config))

    def test_doctor_reports_contract_without_requiring_input(self) -> None:
        checks = collect_doctor_checks(
            self.config,
            data_dir=Path("missing-data-dir-for-test"),
        )
        report = render_doctor_report(checks)

        self.assertIn("Neko Core doctor", report)
        self.assertTrue(any(check.name == "config" and check.status == "ok" for check in checks))
        self.assertTrue(any(check.name == "input" and check.status == "warn" for check in checks))

    def test_capability_registry_separates_runtime_from_development(self) -> None:
        capabilities = collect_capabilities(self.config)
        report = render_capabilities(capabilities)

        self.assertIn("contest_io", report)
        self.assertTrue(any(item.name == "web_research" and item.phase == "development" for item in capabilities))
        self.assertTrue(any(item.name == "tournament" and item.phase == "runtime" for item in capabilities))

    def test_workflow_registry_resolves_named_profiles(self) -> None:
        workflows = list_workflows(self.config)
        report = render_workflows(workflows)
        quick = resolve_workflow(self.config, "quick-dry-run")
        contest = resolve_workflow(self.config, "contest-auto")

        self.assertIn("Neko Core workflows", report)
        self.assertTrue(quick.dry_run)
        self.assertEqual(contest.phase, "runtime")
        self.assertEqual(contest.strategy, "auto")

    def test_workflow_registry_rejects_unknown_name(self) -> None:
        with self.assertRaises(ValueError):
            resolve_workflow(self.config, "missing-workflow")

    def test_normalize_answer_prefers_last_visible_valid_letter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0003",
                            "question": "Cau hoi mau?",
                            "choices": ["Mot", "Hai", "Ba", "Bon"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        self.assertEqual(normalize_answer("Reasoning says A. Final: C", problem), "C")

    def test_normalize_answer_ignores_article_letters_in_long_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0005",
                            "question": "Cau hoi mau?",
                            "choices": ["Mot", "Hai", "Ba", "Bon"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        self.assertIsNone(
            normalize_answer("The question asks for a crime in the context.", problem)
        )

    def test_prediction_validation_rejects_invalid_letters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0004",
                            "question": "Cau hoi mau?",
                            "choices": ["Mot", "Hai"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        summary = validate_predictions(
            [problem],
            [
                Prediction(
                    qid="test_0004",
                    answer="C",
                    model="test",
                    raw_answer="C",
                    strategy="test",
                    confidence=1.0,
                )
            ],
            self.config,
        )

        self.assertFalse(summary.valid)
        self.assertEqual(summary.issues[0].code, "invalid_answer_letter")

    def test_solver_direct_uses_configured_prompt_without_runtime_name_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0006",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        prediction = solve_problem(
            problem,
            FakeClient(["B"]),  # type: ignore[arg-type]
            strategy="direct",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "B")
        self.assertEqual(prediction.strategy, "gemma_direct")

    def test_solver_repairs_invalid_model_output_before_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0007",
                            "question": "Question: calculate the answer.",
                            "choices": ["One", "Two", "Three", "Four"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]

        prediction = solve_problem(
            problem,
            FakeClient(["I need to calculate this carefully first.", "C"]),  # type: ignore[arg-type]
            strategy="direct",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "C")
        self.assertEqual(prediction.strategy, "gemma_repaired")
        self.assertEqual(prediction.attempts, 2)


if __name__ == "__main__":
    unittest.main()
