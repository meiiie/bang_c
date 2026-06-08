from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from hackaithon_c.branding import ascii_logo, version_line
from hackaithon_c.capabilities import collect_capabilities, render_capabilities
from hackaithon_c.classifier import classify_problem
from hackaithon_c.compare import compare_trace_dirs, render_trace_comparison
from hackaithon_c.config import LOCAL_CONFIG_DIR, LOCAL_CONFIG_NAME, load_config
from hackaithon_c.doctor import collect_doctor_checks, render_doctor_report
from hackaithon_c.evaluation import validate_predictions, write_summary
from hackaithon_c.exporter import write_predictions, write_trace
from hackaithon_c.loader import filter_problems_by_qids, load_problems
from hackaithon_c.manifest import build_run_manifest, write_run_manifest
from hackaithon_c.model_inventory import (
    classify_model,
    collect_model_inventory,
    render_model_inventory,
)
from hackaithon_c.normalize import normalize_answer
from hackaithon_c.prompting import build_prompt
from hackaithon_c.project import init_project
from hackaithon_c.review import render_trace_review, review_trace_dir
from hackaithon_c.review_tasks import (
    build_review_tasks,
    render_review_tasks,
    write_review_tasks_json,
)
from hackaithon_c.schema import Prediction, TraceStep
from hackaithon_c.session import (
    discover_run_sessions,
    load_run_session_record,
    prepare_run_session,
    render_run_session_detail,
    render_run_sessions,
    write_run_report,
)
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

    def _write_trace_bundle(
        self,
        temp_dir: str,
        name: str,
        input_path: Path,
        *,
        answer: str = "A",
        confidence: float = 0.8,
    ) -> Path:
        problem = load_problems(input_path)[0]
        prediction = Prediction(
            qid=problem.qid,
            answer=answer,
            model="heuristic",
            raw_answer=answer,
            strategy="fallback_overlap",
            confidence=confidence,
            trace=(
                TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True", answer),
            ),
        )
        trace_dir = Path(temp_dir) / name
        output_path = Path(temp_dir) / f"{name}-output" / "pred.csv"
        summary = validate_predictions(
            [problem],
            [prediction],
            self.config,
            trace_enabled=True,
        )
        write_trace(trace_dir, [prediction])
        write_summary(trace_dir / "run-summary.json", summary)
        write_run_manifest(
            trace_dir / "run-manifest.json",
            build_run_manifest(
                config=self.config,
                input_path=input_path,
                output_path=output_path,
                trace_dir=trace_dir,
                workflow="quick-dry-run",
                strategy="auto",
                dry_run=True,
                verify=False,
                model="heuristic",
                limit=1,
                summary=summary,
                argv=("--workflow", "quick-dry-run"),
            ),
        )
        return trace_dir

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

    def test_problem_filter_selects_requested_qids_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {"qid": "a", "question": "A?", "choices": ["yes", "no"]},
                        {"qid": "b", "question": "B?", "choices": ["yes", "no"]},
                        {"qid": "c", "question": "C?", "choices": ["yes", "no"]},
                    ]
                ),
                encoding="utf-8",
            )
            problems = load_problems(path)

        filtered = filter_problems_by_qids(problems, ("c", "a"))

        self.assertEqual([problem.qid for problem in filtered], ["c", "a"])
        with self.assertRaises(ValueError):
            filter_problems_by_qids(problems, ("missing",))

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
        self.assertIn("gemma-4", self.config.allowed_model_families)
        self.assertIn("bge-m3", self.config.allowed_embedding_families)
        self.assertGreater(self.config.rubric["contract"], 0)
        self.assertTrue(ascii_logo(self.config))
        self.assertIn("Neko Core", version_line(self.config))

    def test_local_project_config_is_preferred_from_current_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_dir = root / LOCAL_CONFIG_DIR
            local_dir.mkdir()
            local_config = json.loads(json.dumps(self.config.raw))
            local_config["brand"]["name"] = "Local Neko"
            (local_dir / LOCAL_CONFIG_NAME).write_text(
                json.dumps(local_config),
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                loaded = load_config()
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(loaded.brand_name, "Local Neko")
        self.assertEqual(loaded.path.name, LOCAL_CONFIG_NAME)

    def test_project_init_creates_local_config_and_respects_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = init_project(root)
            first_raw = json.loads(first.config_path.read_text(encoding="utf-8"))

            edited_raw = json.loads(json.dumps(first_raw))
            edited_raw["brand"]["name"] = "Edited Neko"
            first.config_path.write_text(json.dumps(edited_raw), encoding="utf-8")

            second = init_project(root)
            kept_raw = json.loads(second.config_path.read_text(encoding="utf-8"))

            third = init_project(root, force=True)
            reset_raw = json.loads(third.config_path.read_text(encoding="utf-8"))

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(kept_raw["brand"]["name"], "Edited Neko")
        self.assertTrue(third.created)
        self.assertEqual(reset_raw["brand"]["name"], self.config.brand_name)

    def test_run_session_report_records_artifacts_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "run"
            session = prepare_run_session(root)
            summary = validate_predictions(
                [],
                [],
                self.config,
                trace_enabled=True,
            )
            write_run_report(
                session.report_path,
                input_path=Path("input.json"),
                output_path=session.output_dir / "pred.csv",
                trace_dir=session.trace_dir,
                workflow="quick-dry-run",
                strategy="auto",
                dry_run=True,
                verify=False,
                model="heuristic",
                summary=summary,
                review=review_trace_dir(session.trace_dir),
                review_tasks_path=session.review_tasks_markdown_path,
            )
            report = session.report_path.read_text(encoding="utf-8")

        self.assertEqual(session.output_dir, root / "output")
        self.assertEqual(session.trace_dir, root / "traces")
        self.assertIn("# Neko Core Run Report", report)
        self.assertIn("- Workflow: quick-dry-run", report)
        self.assertIn("- Verdict: FAIL", report)
        self.assertIn("- Review tasks:", report)

    def test_run_session_reader_lists_resume_ready_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "public_test.json"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_session_1",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(input_path)[0]
            prediction = Prediction(
                qid=problem.qid,
                answer="A",
                model="heuristic",
                raw_answer="A",
                strategy="fallback_overlap",
                confidence=0.2,
                trace=(
                    TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                    TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True", "A"),
                ),
            )
            root = Path(temp_dir) / "run-session"
            session = prepare_run_session(root)
            output_path = session.output_dir / "pred.csv"
            summary = validate_predictions(
                [problem],
                [prediction],
                self.config,
                trace_enabled=True,
            )
            write_trace(session.trace_dir, [prediction])
            write_summary(session.trace_dir / "run-summary.json", summary)
            write_run_manifest(
                session.trace_dir / "run-manifest.json",
                build_run_manifest(
                    config=self.config,
                    input_path=input_path,
                    output_path=output_path,
                    trace_dir=session.trace_dir,
                    workflow="quick-dry-run",
                    strategy="auto",
                    dry_run=True,
                    verify=False,
                    model="heuristic",
                    limit=1,
                    summary=summary,
                    argv=("--workflow", "quick-dry-run"),
                ),
            )
            review = review_trace_dir(session.trace_dir)
            tasks = build_review_tasks(review)
            write_review_tasks_json(session.review_tasks_json_path, tasks)
            write_run_report(
                session.report_path,
                input_path=input_path,
                output_path=output_path,
                trace_dir=session.trace_dir,
                workflow="quick-dry-run",
                strategy="auto",
                dry_run=True,
                verify=False,
                model="heuristic",
                summary=summary,
                review=review,
                review_tasks_path=session.review_tasks_markdown_path,
            )

            record = load_run_session_record(root)
            records = discover_run_sessions(Path(temp_dir))
            listing = render_run_sessions(records, root=Path(temp_dir))
            detail = render_run_session_detail(record) if record else ""

        self.assertIsNotNone(record)
        self.assertEqual(record.workflow if record else "", "quick-dry-run")
        self.assertEqual(record.review_task_count if record else 0, 1)
        self.assertIn("Neko Core Run Sessions", listing)
        self.assertIn("run-session", listing)
        self.assertIn("Neko Core Session", detail)
        self.assertIn("resolve-tasks.ps1", detail)

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
        self.assertIn("model_inventory", report)
        self.assertTrue(any(item.name == "web_research" and item.phase == "development" for item in capabilities))
        self.assertTrue(any(item.name == "tournament" and item.phase == "runtime" for item in capabilities))

    def test_model_inventory_filters_bang_c_allowed_models(self) -> None:
        payload = {
            "data": [
                {"id": "google/gemma-4-31b-it"},
                {"id": "qwen/qwen3.5-8b-instruct"},
                {"id": "qwen/qwen3.5-14b-instruct"},
                {"id": "baai/bge-m3"},
                {"id": "qwen/qwen-rerank"},
                {"id": "nvidia/nv-embed-v1"},
            ]
        }

        report = collect_model_inventory(self.config, payload=payload)
        rendered = render_model_inventory(report)
        allowed_ids = {item.model_id for item in report.items if item.allowed}
        blocked = classify_model("qwen/qwen3.5-14b-instruct")

        self.assertEqual(report.status, "ok")
        self.assertTrue(report.selected_model_allowed)
        self.assertIn("google/gemma-4-31b-it", allowed_ids)
        self.assertIn("qwen/qwen3.5-8b-instruct", allowed_ids)
        self.assertIn("baai/bge-m3", allowed_ids)
        self.assertIn("qwen/qwen-rerank", allowed_ids)
        self.assertFalse(blocked.allowed)
        self.assertIn("Allowed LLM models", rendered)
        self.assertNotIn("nvidia/nv-embed-v1: ", rendered)

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
        self.assertEqual([step.role for step in prediction.trace], ["classifier", "solver"])

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
        self.assertEqual([step.role for step in prediction.trace], ["classifier", "solver", "repair"])

    def test_trace_export_contains_structured_agent_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0008",
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
                FakeClient(["A", "B"]),  # type: ignore[arg-type]
                strategy="verify",
                config=self.config,
            )
            trace_dir = Path(temp_dir) / "traces"
            write_trace(trace_dir, [prediction])
            rows = [
                json.loads(line)
                for line in (trace_dir / "predictions.trace.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

        self.assertEqual(prediction.answer, "B")
        self.assertEqual([step.role for step in prediction.trace], ["classifier", "solver", "verifier"])
        self.assertEqual(rows[0]["trace"][0]["role"], "classifier")
        self.assertEqual(rows[0]["trace"][-1]["answer"], "B")

    def test_trace_review_warns_on_low_confidence_without_failing_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0009",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]
            prediction = Prediction(
                qid=problem.qid,
                answer="A",
                model="heuristic",
                raw_answer="A",
                strategy="fallback_overlap",
                confidence=0.4,
                trace=(
                    TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                    TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True", "A"),
                ),
            )
            trace_dir = Path(temp_dir) / "traces"
            write_trace(trace_dir, [prediction])
            write_summary(
                trace_dir / "run-summary.json",
                validate_predictions([problem], [prediction], self.config, trace_enabled=True),
            )

            review = review_trace_dir(trace_dir)
            rendered = render_trace_review(review)

        self.assertEqual(review.verdict, "warn")
        self.assertIn("low_confidence", rendered)

    def test_review_tasks_turn_trace_findings_into_action_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0013",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]
            prediction = Prediction(
                qid=problem.qid,
                answer="A",
                model="heuristic",
                raw_answer="A",
                strategy="fallback_overlap",
                confidence=0.2,
                trace=(
                    TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                    TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True", "A"),
                ),
            )
            trace_dir = Path(temp_dir) / "traces"
            write_trace(trace_dir, [prediction])
            write_summary(
                trace_dir / "run-summary.json",
                validate_predictions([problem], [prediction], self.config, trace_enabled=True),
            )
            review = review_trace_dir(trace_dir)
            tasks = build_review_tasks(review)
            rendered = render_review_tasks(tasks)
            tasks_path = Path(temp_dir) / "review-tasks.json"
            write_review_tasks_json(tasks_path, tasks)
            payload = json.loads(tasks_path.read_text(encoding="utf-8"))

        self.assertTrue(tasks)
        self.assertEqual(payload["schema_version"], "neko_core.review_tasks.v1")
        self.assertIn("test_0013", rendered)
        self.assertTrue(any(task.finding_code == "low_confidence" for task in tasks))

    def test_run_manifest_records_reproducible_run_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0010",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]
            prediction = Prediction(
                qid=problem.qid,
                answer="A",
                model="heuristic",
                raw_answer="A",
                strategy="fallback_overlap",
                confidence=0.8,
                trace=(
                    TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                    TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True", "A"),
                ),
            )
            trace_dir = Path(temp_dir) / "traces"
            output_path = Path(temp_dir) / "output" / "pred.csv"
            summary = validate_predictions(
                [problem],
                [prediction],
                self.config,
                trace_enabled=True,
            )
            write_trace(trace_dir, [prediction])
            write_summary(trace_dir / "run-summary.json", summary)
            write_run_manifest(
                trace_dir / "run-manifest.json",
                build_run_manifest(
                    config=self.config,
                    input_path=path,
                    output_path=output_path,
                    trace_dir=trace_dir,
                    workflow="quick-dry-run",
                    strategy="auto",
                    dry_run=True,
                    verify=False,
                    model="heuristic",
                    limit=1,
                    summary=summary,
                    argv=("--workflow", "quick-dry-run"),
                ),
            )
            manifest = json.loads(
                (trace_dir / "run-manifest.json").read_text(encoding="utf-8")
            )
            review = review_trace_dir(trace_dir)

        self.assertEqual(manifest["schema_version"], "neko_core.run_manifest.v1")
        self.assertEqual(manifest["workflow"], "quick-dry-run")
        self.assertEqual(len(manifest["input_sha256"]), 64)
        self.assertFalse(any(finding.code == "missing_manifest" for finding in review.findings))

    def test_trace_comparison_passes_for_identical_prediction_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0011",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            left = self._write_trace_bundle(temp_dir, "left", path, answer="A")
            right = self._write_trace_bundle(temp_dir, "right", path, answer="A")

            comparison = compare_trace_dirs(left, right)
            rendered = render_trace_comparison(comparison)

        self.assertEqual(comparison.verdict, "pass")
        self.assertEqual(comparison.changed_answers, 0)
        self.assertIn("trace_match", rendered)

    def test_trace_comparison_warns_when_answers_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0012",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            left = self._write_trace_bundle(temp_dir, "left", path, answer="A")
            right = self._write_trace_bundle(temp_dir, "right", path, answer="B")

            comparison = compare_trace_dirs(left, right)
            rendered = render_trace_comparison(comparison)

        self.assertEqual(comparison.verdict, "warn")
        self.assertEqual(comparison.changed_answers, 1)
        self.assertIn("answer_changed", rendered)

    def test_trace_comparison_can_scope_to_review_task_qids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_0014a",
                            "question": "Question one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        },
                        {
                            "qid": "test_0014b",
                            "question": "Question two.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            problems = load_problems(path)
            left_predictions = [
                Prediction(
                    qid=problems[0].qid,
                    answer="A",
                    model="heuristic",
                    raw_answer="A",
                    strategy="fallback_overlap",
                    confidence=0.8,
                    trace=(
                        TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                        TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True"),
                    ),
                ),
                Prediction(
                    qid=problems[1].qid,
                    answer="B",
                    model="heuristic",
                    raw_answer="B",
                    strategy="fallback_overlap",
                    confidence=0.8,
                    trace=(
                        TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                        TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True"),
                    ),
                ),
            ]
            right_predictions = [
                left_predictions[0],
                Prediction(
                    qid=problems[1].qid,
                    answer="C",
                    model="heuristic",
                    raw_answer="C",
                    strategy="fallback_overlap",
                    confidence=0.8,
                    trace=(
                        TraceStep("classifier", "profile_problem", "completed", "kind=short"),
                        TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True"),
                    ),
                ),
            ]
            left_dir = Path(temp_dir) / "left"
            right_dir = Path(temp_dir) / "right"
            output_path = Path(temp_dir) / "output" / "pred.csv"
            for trace_dir, predictions in (
                (left_dir, left_predictions),
                (right_dir, right_predictions),
            ):
                summary = validate_predictions(
                    problems,
                    predictions,
                    self.config,
                    trace_enabled=True,
                )
                write_trace(trace_dir, predictions)
                write_summary(trace_dir / "run-summary.json", summary)
                write_run_manifest(
                    trace_dir / "run-manifest.json",
                    build_run_manifest(
                        config=self.config,
                        input_path=path,
                        output_path=output_path,
                        trace_dir=trace_dir,
                        workflow="quick-dry-run",
                        strategy="auto",
                        dry_run=True,
                        verify=False,
                        model="heuristic",
                        limit=None,
                        summary=summary,
                        argv=("--workflow", "quick-dry-run"),
                    ),
                )

            full = compare_trace_dirs(left_dir, right_dir)
            scoped = compare_trace_dirs(left_dir, right_dir, qids=("test_0014a",))
            missing = compare_trace_dirs(left_dir, right_dir, qids=("missing",))

        self.assertEqual(full.changed_answers, 1)
        self.assertEqual(scoped.verdict, "pass")
        self.assertEqual(scoped.changed_answers, 0)
        self.assertEqual(missing.verdict, "fail")
        self.assertTrue(any(finding.code == "left_missing_selected_qid" for finding in missing.findings))

    def test_trace_review_fails_when_trace_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review = review_trace_dir(Path(temp_dir) / "missing-traces")

        self.assertEqual(review.verdict, "fail")
        self.assertTrue(any(finding.code == "missing_summary" for finding in review.findings))


if __name__ == "__main__":
    unittest.main()
