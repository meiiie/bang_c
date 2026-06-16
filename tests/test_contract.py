from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from hackaithon_c.agents import list_agents, render_agent_detail, render_agents, resolve_agent
from hackaithon_c.branding import ascii_logo, version_line
from hackaithon_c.calculation import list_calculation_decision_rules, list_calculation_rules
from hackaithon_c.capabilities import collect_capabilities, render_capabilities
from hackaithon_c.checkpoint import (
    append_checkpoint,
    load_checkpoint,
    verify_checkpoint_meta,
    write_checkpoint_meta,
)
from hackaithon_c.classifier import classify_problem
from hackaithon_c.command_registry import (
    list_commands,
    render_command_detail,
    render_commands,
    resolve_command,
)
from hackaithon_c.compare import compare_trace_dirs, render_trace_comparison
from hackaithon_c.config import LOCAL_CONFIG_DIR, LOCAL_CONFIG_NAME, load_config
from hackaithon_c.doctor import collect_doctor_checks, render_doctor_report
from hackaithon_c.evaluation import validate_predictions, write_summary
from hackaithon_c.evidence import adjudicate_date_evidence
from hackaithon_c.events import build_event, load_events, render_events, write_events
from hackaithon_c.exporter import write_predictions, write_trace
from hackaithon_c.loader import filter_problems_by_qids, load_problems
from hackaithon_c.local_client import LocalLlamaChatClient, LocalLlamaConfig
from hackaithon_c.manifest import build_run_manifest, write_run_manifest
from hackaithon_c.model_inventory import (
    DEFAULT_POLICY,
    FamilyRule,
    ModelPolicy,
    classify_model,
    collect_model_inventory,
    policy_from_config,
    render_model_inventory,
)
from hackaithon_c.normalize import normalize_answer
from hackaithon_c.nvidia_client import NvidiaConfig, _retry_delay_seconds
from hackaithon_c.policy import evaluate_policy, evaluate_policy_specs, render_policy_report
from hackaithon_c.prompting import build_prompt, build_verifier_prompt, tournament_variants
from hackaithon_c.project import init_project
from hackaithon_c.principles import list_principle_rules
from hackaithon_c.review import render_trace_review, review_trace_dir
from hackaithon_c.review_tasks import (
    build_review_tasks,
    render_review_tasks,
    write_review_tasks_json,
)
from hackaithon_c.run import (
    _is_retryable_prediction,
    _normalize_cli_argv,
    _problem_retry_delay_seconds,
    apply_yolo_defaults,
    main as run_main,
    parse_args,
    render_runtime_profiles,
    validate_runtime_model,
)
from hackaithon_c.schema import Prediction, Problem, TraceStep
from hackaithon_c.session import (
    discover_run_sessions,
    load_run_session_record,
    prepare_run_session,
    render_run_session_detail,
    render_run_sessions,
    write_run_report,
)
from hackaithon_c.solver import solve_problem
from hackaithon_c.submission import check_submission_file, render_submission_check
from hackaithon_c.tool_registry import (
    list_tools,
    render_tool_detail,
    render_tools,
    resolve_tool,
)
from hackaithon_c.workflows import list_workflows, render_workflows, resolve_workflow
from hackaithon_c.text import normalize_text


class FakeClient:
    model = "fake/gemma-4"

    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 12, letters=None) -> str:
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return self.answers.pop(0)


class FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


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
            raw = path.read_bytes()
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(raw, b"qid,answer\ntest_0001,C\n")
        self.assertEqual(rows, [{"qid": "test_0001", "answer": "C"}])

    def test_submission_check_validates_filename_header_and_row_alphabet(self) -> None:
        problems = [
            Problem(
                qid="test_0001",
                question="Pick J.",
                choices=tuple(f"Choice {letter}" for letter in "ABCDEFGHIJ"),
            )
        ]
        prediction = Prediction(
            qid="test_0001",
            answer="J",
            model="heuristic",
            raw_answer="J",
            strategy="test",
            confidence=1.0,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pred.csv"
            write_predictions(path, [prediction])
            check = check_submission_file(path, problems, self.config)
            rendered = render_submission_check(check)

            wrong_name = Path(temp_dir) / "renamed.csv"
            write_predictions(wrong_name, [prediction])
            wrong_check = check_submission_file(wrong_name, problems, self.config)

        self.assertTrue(check.valid)
        self.assertIn("Issues: none", rendered)
        self.assertFalse(wrong_check.valid)
        self.assertEqual(wrong_check.issues[0].code, "wrong_file_name")

    def test_submission_check_rejects_quoted_or_bom_csv(self) -> None:
        problems = [
            Problem(
                qid="test_0001",
                question="Pick A.",
                choices=("A choice", "B choice", "C choice", "D choice"),
            )
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            quoted = Path(temp_dir) / "pred.csv"
            quoted.write_text('"qid","answer"\n"test_0001","A"\n', encoding="utf-8")
            quoted_check = check_submission_file(quoted, problems, self.config)

            bom = Path(temp_dir) / "pred.csv"
            bom.write_bytes(b"\xef\xbb\xbfqid,answer\ntest_0001,A\n")
            bom_check = check_submission_file(bom, problems, self.config)

        self.assertFalse(quoted_check.valid)
        self.assertIn("quoted_csv", {issue.code for issue in quoted_check.issues})
        self.assertIn("invalid_raw_header", {issue.code for issue in quoted_check.issues})
        self.assertFalse(bom_check.valid)
        self.assertIn("utf8_bom", {issue.code for issue in bom_check.issues})

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

    def test_classifier_routes_calculation_to_tournament_capable_profile(self) -> None:
        problem = Problem(
            qid="test_calc_profile",
            question="Tinh gia tri cua 2 + 2 la bao nhieu?",
            choices=("3", "4", "5", "6"),
        )

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "calculation")
        self.assertTrue(profile.should_verify)
        self.assertTrue(profile.should_tournament)

    def test_classifier_does_not_treat_province_tinh_as_calculation(self) -> None:
        problem = Problem(
            qid="test_province_tinh",
            question="Khi doi can cuoc cong dan tai cap tinh Ca Mau, can nop giay to nao?",
            choices=("Ho so A", "Ho so B", "Ho so C", "Ho so D"),
        )

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "short")
        self.assertIn("has_legal_admin", profile.features)
        self.assertNotIn("has_calculation", profile.features)
        self.assertIn("ignored_calculation_marker=tinh", profile.diagnostics)

    def test_classifier_routes_negative_before_broad_value_marker(self) -> None:
        problem = Problem(
            qid="test_negative_value",
            question="Chon dap an sai ve gia tri tu tuong cua tac pham.",
            choices=("Noi dung A", "Noi dung B", "Noi dung C", "Noi dung D"),
        )

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "negative")
        self.assertIn("has_negative", profile.features)
        self.assertNotIn("has_calculation", profile.features)
        self.assertIn("ignored_calculation_marker=gia tri", profile.diagnostics)

    def test_classifier_does_not_treat_phuong_sai_as_negative(self) -> None:
        problem = Problem(
            qid="test_phuong_sai",
            question="Trong thong ke, phuong sai cua du lieu 1, 2, 3 la bao nhieu?",
            choices=("0", "1", "2", "3", "4"),
        )

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "calculation")
        self.assertIn("has_calculation", profile.features)
        self.assertNotIn("has_negative", profile.features)
        self.assertIn("ignored_negative_marker=sai", profile.diagnostics)

    def test_classifier_marks_many_choice_calculation_as_compound(self) -> None:
        problem = Problem(
            qid="test_compound_many_choice_calculation",
            question="Tinh 2 + 2 bang bao nhieu?",
            choices=("0", "1", "2", "3", "4", "5"),
        )

        profile = classify_problem(problem, self.config)

        self.assertEqual(profile.kind, "calculation")
        self.assertIn("has_many_choices", profile.features)
        self.assertIn("has_calculation", profile.features)
        self.assertEqual(tournament_variants(profile)[0], "calculation")

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
        self.assertEqual(self.config.active_profile, "gemma26b-q4-local")
        self.assertEqual(self.config.provider, "local_llamacpp")
        self.assertEqual(
            self.config.default_model,
            "google/gemma-4-26B-A4B-it-qat-q4_0-gguf:Q4_0",
        )
        self.assertEqual(self.config.api_model, "google/gemma-4-31b-it")
        self.assertEqual(self.config.local_model_file, "gemma-4-26B_q4_0-it.gguf")
        self.assertEqual(self.config.local_model_path, "/models/gemma-4-26B_q4_0-it.gguf")
        self.assertIn("gemma-4", self.config.allowed_model_families)
        self.assertIn("bge-m3", self.config.allowed_embedding_families)
        self.assertEqual(self.config.max_retries, 6)
        self.assertEqual(self.config.retry_base_delay_seconds, 1.5)
        self.assertEqual(self.config.retry_max_delay_seconds, 30.0)
        self.assertEqual(self.config.problem_max_retries, 2)
        self.assertEqual(self.config.problem_retry_base_delay_seconds, 5.0)
        self.assertEqual(self.config.problem_retry_max_delay_seconds, 60.0)
        self.assertGreater(self.config.rubric["contract"], 0)
        self.assertTrue(ascii_logo(self.config))
        self.assertIn("Neko Core", version_line(self.config))

    def test_runtime_profiles_can_override_provider_without_source_changes(self) -> None:
        api_config = load_config(profile="nvidia-gemma31b-api")
        rendered = render_runtime_profiles(self.config)

        self.assertEqual(api_config.active_profile, "nvidia-gemma31b-api")
        self.assertEqual(api_config.provider, "nvidia")
        self.assertEqual(api_config.default_model, "google/gemma-4-31b-it")
        self.assertIn("gemma26b-q4-local (active)", rendered)
        self.assertIn("nvidia-gemma31b-api", rendered)

        with self.assertRaisesRegex(ValueError, "Unknown runtime profile"):
            load_config(profile="missing-profile")

    def test_package_exposes_neko_command_alias(self) -> None:
        pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('neko = "hackaithon_c.run:main"', pyproject)
        self.assertIn('neko-core = "hackaithon_c.run:main"', pyproject)

    def test_cli_accepts_core_namespace_alias(self) -> None:
        self.assertEqual(_normalize_cli_argv(("core", "--doctor")), ("--doctor",))
        self.assertEqual(_normalize_cli_argv(("--doctor",)), ("--doctor",))
        self.assertEqual(parse_args(("--profile", "nvidia-gemma31b-api")).profile, "nvidia-gemma31b-api")

    def test_docker_default_run_is_checkpointed_and_auto_resumable(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        gemma_dockerfile = Path("Dockerfile.gemma-local").read_text(encoding="utf-8")

        self.assertIn('"contest-strict"', dockerfile)
        self.assertIn('"--run-dir"', dockerfile)
        self.assertIn('"/output/neko-run"', dockerfile)
        self.assertIn('"--auto-resume"', dockerfile)
        self.assertIn('"--checkpoint-every"', dockerfile)
        self.assertIn("HACKC_PROFILE=nvidia-gemma31b-api", dockerfile)
        self.assertIn("HACKC_PROVIDER=nvidia", dockerfile)
        self.assertIn("HACKC_PROVIDER=local_llamacpp", gemma_dockerfile)
        self.assertIn("gemma-4-26B_q4_0-it.gguf", gemma_dockerfile)
        self.assertIn("LLAMA_CPP_EXTRA_INDEX_URL", gemma_dockerfile)
        self.assertIn("--mount=type=secret,id=HF_TOKEN", gemma_dockerfile)

    def test_problem_retry_helpers_retry_transient_fallbacks_only(self) -> None:
        transient = Prediction(
            qid="retry",
            answer="A",
            model="fake",
            raw_answer="solver_error",
            strategy="fallback_overlap_after_error",
            confidence=0.1,
            fallback_reason="RuntimeError",
        )
        invalid = Prediction(
            qid="invalid",
            answer="A",
            model="fake",
            raw_answer="invalid output",
            strategy="fallback_overlap_after_invalid_llm",
            confidence=0.1,
            fallback_reason="invalid_evidence",
        )

        self.assertTrue(_is_retryable_prediction(transient))
        self.assertFalse(_is_retryable_prediction(invalid))
        self.assertEqual(_problem_retry_delay_seconds(0, self.config), 5.0)
        self.assertEqual(_problem_retry_delay_seconds(10, self.config), 60.0)

    def test_nvidia_retry_delay_uses_retry_after_and_exponential_cap(self) -> None:
        config = NvidiaConfig(
            api_key="test",
            retry_base_delay_seconds=2.0,
            retry_max_delay_seconds=10.0,
        )

        self.assertEqual(
            _retry_delay_seconds(0, FakeResponse({"Retry-After": "7"}), config),
            7.0,
        )
        self.assertEqual(
            _retry_delay_seconds(0, FakeResponse({"Retry-After": "99"}), config),
            10.0,
        )
        self.assertEqual(_retry_delay_seconds(3, None, config), 10.0)

    def test_local_llama_client_fails_closed_when_model_file_is_missing(self) -> None:
        client = LocalLlamaChatClient(
            LocalLlamaConfig(
                model_id="google/gemma-4-26B-A4B-it-qat-q4_0-gguf:Q4_0",
                model_path=Path("missing-model-for-test.gguf"),
            )
        )

        with self.assertRaisesRegex(RuntimeError, "Local model file not found"):
            client.complete("system", "user")

    def test_text_normalization_handles_vietnamese_d_stroke(self) -> None:
        self.assertEqual(
            normalize_text("Tốc độ, độ cao, đang được đổ đầy"),
            "toc do, do cao, dang duoc do day",
        )

    def test_calculation_adjudicator_uses_named_rule_registry(self) -> None:
        rules = list_calculation_rules()
        decision_rules = list_calculation_decision_rules()

        self.assertIn("gdp_inflation", {rule.name for rule in rules})
        self.assertIn("cylinder_fill_rate", {rule.name for rule in rules})
        self.assertEqual(decision_rules, ())  # per-question depreciable hard-code removed (overfit)
        self.assertIn("buffer_ph", {rule.name for rule in rules})
        self.assertEqual(len({rule.name for rule in rules}), len(rules))

    def test_packaged_default_config_matches_repo_default(self) -> None:
        repo_config = Path("configs/default.json")
        packaged_config = Path("src/hackaithon_c/resources/default.json")

        self.assertEqual(
            json.loads(repo_config.read_text(encoding="utf-8")),
            json.loads(packaged_config.read_text(encoding="utf-8")),
        )

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
            write_events(
                session.events_path,
                (
                    build_event(
                        "session_started",
                        "started",
                        "Run session started.",
                    ),
                ),
            )
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
        self.assertEqual(record.event_count if record else 0, 1)
        self.assertIn("Neko Core Run Sessions", listing)
        self.assertIn("run-session", listing)
        self.assertIn("Neko Core Session", detail)
        self.assertIn("--events", detail)
        self.assertIn("resolve-tasks.ps1", detail)

    def test_checkpoint_round_trips_predictions_and_rejects_input_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "public_test.json"
            changed_input_path = root / "changed_public_test.json"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_checkpoint_1",
                            "question": "Which answer?",
                            "choices": ["A one", "B two"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            changed_input_path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_checkpoint_1",
                            "question": "Which changed answer?",
                            "choices": ["A one", "B two"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            prediction = Prediction(
                qid="test_checkpoint_1",
                answer="A",
                model="heuristic",
                raw_answer="A",
                strategy="fallback_overlap",
                confidence=0.8,
                trace=(TraceStep("solver", "heuristic_fallback", "completed", "dry_run=True", "A"),),
            )
            trace_dir = root / "traces"

            write_checkpoint_meta(
                trace_dir,
                config=self.config,
                input_path=input_path,
                workflow="quick-dry-run",
                strategy="auto",
                dry_run=True,
                verify=False,
                model="heuristic",
                total_problems=1,
            )
            append_checkpoint(trace_dir, [prediction])
            loaded = load_checkpoint(trace_dir)

            self.assertEqual(loaded["test_checkpoint_1"].answer, "A")
            self.assertEqual(loaded["test_checkpoint_1"].trace[0].role, "solver")
            verify_checkpoint_meta(
                trace_dir,
                config=self.config,
                input_path=input_path,
                workflow="quick-dry-run",
                strategy="auto",
                dry_run=True,
                verify=False,
                model="heuristic",
                total_problems=1,
            )
            with self.assertRaises(ValueError):
                verify_checkpoint_meta(
                    trace_dir,
                    config=self.config,
                    input_path=changed_input_path,
                    workflow="quick-dry-run",
                    strategy="auto",
                    dry_run=True,
                    verify=False,
                    model="heuristic",
                    total_problems=1,
                )

    def test_run_event_log_round_trips_as_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            write_events(
                path,
                (
                    build_event(
                        "session_started",
                        "started",
                        "Run session started.",
                        payload={"workflow": "quick-dry-run"},
                    ),
                    build_event(
                        "prediction_completed",
                        "completed",
                        "Predicted A.",
                        qid="test_0001",
                        payload={"answer": "A"},
                    ),
                ),
            )
            events = load_events(path)
            rendered = render_events(events, source=path)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].schema_version, "neko_core.run_event.v1")
        self.assertEqual(events[1].qid, "test_0001")
        self.assertIn("prediction_completed [test_0001]", rendered)

    def test_doctor_reports_contract_without_requiring_input(self) -> None:
        checks = collect_doctor_checks(
            self.config,
            data_dir=Path("missing-data-dir-for-test"),
        )
        report = render_doctor_report(checks)

        self.assertIn("Neko Core doctor", report)
        self.assertTrue(any(check.name == "config" and check.status == "ok" for check in checks))
        self.assertTrue(any(check.name == "input" and check.status == "warn" for check in checks))
        self.assertTrue(any(check.name == "provider" and check.detail == "local_llamacpp" for check in checks))
        self.assertTrue(any(check.name == "local_model" and check.status == "warn" for check in checks))

    def test_capability_registry_separates_runtime_from_development(self) -> None:
        capabilities = collect_capabilities(self.config)
        report = render_capabilities(capabilities)

        self.assertIn("contest_io", report)
        self.assertIn("agent_registry", report)
        self.assertIn("tool_registry", report)
        self.assertIn("command_registry", report)
        self.assertIn("policy_audit", report)
        self.assertIn("model_inventory", report)
        self.assertIn("bounded_autopilot", report)
        self.assertTrue(any(item.name == "web_research" and item.phase == "development" for item in capabilities))
        self.assertTrue(any(item.name == "tournament" and item.phase == "runtime" for item in capabilities))

    def test_agent_registry_documents_handoff_boundaries(self) -> None:
        agents = list_agents(self.config)
        rendered = render_agents(agents)
        resolver = resolve_agent(self.config, "task-resolver")
        detail = render_agent_detail(resolver)

        self.assertIn("Neko Core agents", rendered)
        self.assertTrue(any(agent.name == "runner" and agent.phase == "runtime" for agent in agents))
        self.assertTrue(any(agent.name == "session-inspector" and agent.phase == "development" for agent in agents))
        self.assertIn("--compare-qid", detail)
        self.assertIn("task-resolution.json", detail)
        with self.assertRaises(ValueError):
            resolve_agent(self.config, "missing-agent")

    def test_tool_registry_documents_permissions_and_guardrails(self) -> None:
        tools = list_tools(self.config)
        rendered = render_tools(tools)
        exporter = resolve_tool(self.config, "exporter")
        web_research = resolve_tool(self.config, "web-research")
        detail = render_tool_detail(web_research)

        self.assertIn("Neko Core tools", rendered)
        self.assertEqual(exporter.phase, "runtime")
        self.assertIn("/output/pred.csv", exporter.outputs)
        self.assertEqual(web_research.phase, "development")
        self.assertEqual(web_research.status, "external")
        self.assertIn("quarantined-read", detail)
        self.assertIn("cannot write pred.csv", detail)
        with self.assertRaises(ValueError):
            resolve_tool(self.config, "missing-tool")

    def test_command_registry_documents_cli_surface(self) -> None:
        commands = list_commands(self.config)
        rendered = render_commands(commands)
        run = resolve_command(self.config, "run")
        yolo = resolve_command(self.config, "yolo")
        check_submission = resolve_command(self.config, "check-submission")
        trace_review = resolve_command(self.config, "trace-review")
        detail = render_command_detail(run)

        self.assertIn("Neko Core commands", rendered)
        self.assertEqual(run.phase, "runtime")
        self.assertIn("contest-auto", run.example)
        self.assertEqual(yolo.phase, "runtime")
        self.assertIn("does not bypass policy", yolo.guardrail)
        self.assertEqual(check_submission.phase, "cli")
        self.assertIn("instead of hard-coding A-D", check_submission.guardrail)
        self.assertIn("pred.csv", detail)
        self.assertEqual(resolve_command(self.config, "policy").phase, "cli")
        self.assertEqual(trace_review.phase, "development")
        self.assertIn("do not mutate pred.csv", trace_review.guardrail)
        with self.assertRaises(ValueError):
            resolve_command(self.config, "missing-command")

    def test_yolo_mode_applies_bounded_autonomous_defaults(self) -> None:
        args = apply_yolo_defaults(parse_args(("core", "--yolo")))

        self.assertTrue(args.yolo)
        self.assertEqual(args.workflow, "contest-strict")
        self.assertTrue(args.auto_resume)
        self.assertEqual(args.checkpoint_every, 1)
        self.assertEqual(args.output_dir, "/output")
        self.assertEqual(args.run_dir, "/output/neko-run")

    def test_yolo_mode_preserves_explicit_workflow_and_run_dir(self) -> None:
        args = apply_yolo_defaults(
            parse_args(
                (
                    "core",
                    "--yolo",
                    "--workflow",
                    "quick-dry-run",
                    "--input",
                    "public_test.json",
                    "--run-dir",
                    "custom-run",
                    "--checkpoint-every",
                    "0",
                )
            )
        )

        self.assertEqual(args.workflow, "quick-dry-run")
        self.assertEqual(args.run_dir, "custom-run")
        self.assertTrue(args.auto_resume)
        self.assertEqual(args.checkpoint_every, 1)

    def test_policy_audit_keeps_development_tools_quarantined(self) -> None:
        report = evaluate_policy(self.config)
        rendered = render_policy_report(report)

        self.assertEqual(report.verdict, "pass")
        self.assertFalse(report.findings)
        self.assertIn("Neko Core policy", rendered)
        self.assertIn("runtime/development boundaries are consistent", rendered)

    def test_policy_audit_fails_when_external_tool_leaks_into_runtime(self) -> None:
        tools = tuple(
            replace(tool, phase="runtime") if tool.name == "web-research" else tool
            for tool in list_tools(self.config)
        )

        report = evaluate_policy_specs(
            agents=list_agents(self.config),
            tools=tools,
            commands=list_commands(self.config),
        )
        codes = {finding.code for finding in report.findings}

        self.assertEqual(report.verdict, "fail")
        self.assertIn("runtime_external_tool", codes)
        self.assertIn("runtime_quarantined_tool", codes)
        self.assertIn("quarantine_boundary_broken", codes)

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

    def test_runtime_model_validation_fails_closed_on_disallowed_models(self) -> None:
        validate_runtime_model("google/gemma-4-26B-A4B-it-qat-q4_0-gguf:Q4_0", self.config)
        validate_runtime_model("google/gemma-4-31b-it", self.config)
        validate_runtime_model("qwen/qwen3.5-8b-instruct", self.config)

        with self.assertRaisesRegex(ValueError, "not allowed by Bang C rules"):
            validate_runtime_model("qwen/qwen3.5-14b-instruct", self.config)

        with self.assertRaisesRegex(ValueError, "not allowed by Bang C rules"):
            validate_runtime_model("baai/bge-m3", self.config)

    def test_default_config_yields_legacy_model_policy(self) -> None:
        # The shipped config reproduces DEFAULT_POLICY exactly, so the allowlist lives in data.
        policy = policy_from_config(self.config)
        self.assertEqual(policy, DEFAULT_POLICY)

    def test_model_policy_is_config_driven_extensible(self) -> None:
        # A brand-new <=5B family is enabled by a CONFIG edit alone — no code branch per model.
        wide_5b = ModelPolicy(
            llm=(FamilyRule(aliases=("*",), max_params_b=5.0),),
            embedding=(FamilyRule(aliases=("bge-m3",)),),
        )
        self.assertTrue(classify_model("qwen/qwen3-4b-instruct-2507", policy=wide_5b).allowed)
        self.assertTrue(classify_model("microsoft/phi-4-mini-3.8b", policy=wide_5b).allowed)
        self.assertFalse(classify_model("google/gemma-4-26b-it", policy=wide_5b).allowed)
        # The same wildcard family, sourced from config (no Python change):
        cfg = load_config(self._write_policy_config({
            "count_active_for_moe": False,
            "llm_families": [{"aliases": ["*"], "max_params_b": 5.0}],
            "embedding_families": [{"aliases": ["bge-m3"]}],
        }))
        self.assertEqual(policy_from_config(cfg), wide_5b)
        validate_runtime_model("qwen/qwen3-4b-instruct-2507", cfg)
        with self.assertRaisesRegex(ValueError, "not allowed by Bang C rules"):
            validate_runtime_model("google/gemma-4-26b-it", cfg)

    def test_model_policy_counts_active_params_when_configured(self) -> None:
        # Flip a single config flag to score MoE ids on their active (aNb) param count instead of total.
        active_5b = ModelPolicy(
            llm=(FamilyRule(aliases=("gemma-4",), max_params_b=5.0),),
            embedding=(),
            count_active_for_moe=True,
        )
        total_5b = ModelPolicy(
            llm=(FamilyRule(aliases=("gemma-4",), max_params_b=5.0),),
            embedding=(),
            count_active_for_moe=False,
        )
        moe = "google/gemma-4-26b-a4b-it"
        self.assertTrue(classify_model(moe, policy=active_5b).allowed)   # 4B active <= 5B
        self.assertFalse(classify_model(moe, policy=total_5b).allowed)   # 26B total > 5B

    def _write_policy_config(self, policy: dict) -> str:
        import json
        import tempfile
        from pathlib import Path

        base = json.loads(Path(self.config.path).read_text(encoding="utf-8"))
        base.setdefault("runtime", {})["model_policy"] = policy
        tmp = tempfile.mkdtemp(prefix="neko-policy-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        target = Path(tmp) / "policy_override.json"
        target.write_text(json.dumps(base), encoding="utf-8")
        return str(target)

    def test_workflow_registry_resolves_named_profiles(self) -> None:
        workflows = list_workflows(self.config)
        report = render_workflows(workflows)
        quick = resolve_workflow(self.config, "quick-dry-run")
        contest = resolve_workflow(self.config, "contest-auto")
        strict = resolve_workflow(self.config, "contest-strict")

        self.assertIn("Neko Core workflows", report)
        self.assertTrue(quick.dry_run)
        self.assertEqual(contest.phase, "runtime")
        self.assertEqual(contest.strategy, "auto")
        self.assertEqual(strict.strategy, "auto")
        self.assertTrue(strict.verify)

    def test_workflow_registry_rejects_unknown_name(self) -> None:
        with self.assertRaises(ValueError):
            resolve_workflow(self.config, "missing-workflow")

    def test_non_dry_development_workflow_requires_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "public_test.json"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "guard_1",
                            "question": "Pick A.",
                            "choices": ["A", "B", "C", "D"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"HACKC_ALLOW_DEVELOPMENT_WORKFLOW": ""}):
                code = run_main(
                    (
                        "--workflow",
                        "router",
                        "--input",
                        str(input_path),
                        "--output-dir",
                        str(Path(temp_dir) / "out"),
                        "--limit",
                        "0",
                    )
                )

        self.assertEqual(code, 2)

    def test_development_workflow_flag_allows_explicit_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "public_test.json"
            output_dir = Path(temp_dir) / "out"
            input_path.write_text("[]", encoding="utf-8")
            code = run_main(
                (
                    "--workflow",
                    "router",
                    "--allow-development-workflow",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--limit",
                    "0",
                )
            )
            self.assertEqual(code, 0)
            self.assertTrue((output_dir / "pred.csv").exists())

    def test_development_workflow_env_allows_explicit_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "public_test.json"
            output_dir = Path(temp_dir) / "out"
            input_path.write_text("[]", encoding="utf-8")
            with mock.patch.dict(os.environ, {"HACKC_ALLOW_DEVELOPMENT_WORKFLOW": "1"}):
                code = run_main(
                    (
                        "--workflow",
                        "tiered-consistency",
                        "--input",
                        str(input_path),
                        "--output-dir",
                        str(output_dir),
                        "--limit",
                        "0",
                    )
                )
                self.assertEqual(code, 0)
                self.assertTrue((output_dir / "pred.csv").exists())

    def test_dry_development_workflow_remains_available_for_contract_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "public_test.json"
            output_dir = Path(temp_dir) / "out"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "guard_dry",
                            "question": "Pick A.",
                            "choices": ["A", "B", "C", "D"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"HACKC_ALLOW_DEVELOPMENT_WORKFLOW": ""}):
                code = run_main(
                    (
                        "--workflow",
                        "router",
                        "--dry-run",
                        "--input",
                        str(input_path),
                        "--output-dir",
                        str(output_dir),
                        "--limit",
                        "1",
                    )
                )
                self.assertEqual(code, 0)
                self.assertTrue((output_dir / "pred.csv").exists())

    def test_direct_development_strategy_requires_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "public_test.json"
            input_path.write_text("[]", encoding="utf-8")
            with mock.patch.dict(os.environ, {"HACKC_ALLOW_DEVELOPMENT_WORKFLOW": ""}):
                code = run_main(
                    (
                        "--strategy",
                        "tiered",
                        "--input",
                        str(input_path),
                        "--output-dir",
                        str(Path(temp_dir) / "out"),
                        "--limit",
                        "0",
                    )
                )

        self.assertEqual(code, 2)

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

    def test_evidence_prompt_prefers_direct_passage_support(self) -> None:
        problem = self._ambiguous_deuteronomy_problem()
        profile = classify_problem(problem, self.config)

        prompt = build_prompt(problem, profile, config=self.config)
        verifier = build_verifier_prompt(problem, "D")

        self.assertEqual(profile.kind, "reading")
        self.assertIn("clearest direct evidence span", prompt.user_prompt)
        self.assertIn("outside knowledge", prompt.user_prompt)
        self.assertIn("passage-grounded adjudicator", verifier.user_prompt)
        self.assertIn("better supported by the passage wording", verifier.user_prompt)

    def test_verifier_can_override_background_true_answer_for_direct_evidence(self) -> None:
        problem = self._ambiguous_deuteronomy_problem()
        client = FakeClient(["D", "A"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.strategy, "gemma_verified")
        self.assertEqual(prediction.confidence, 0.72)
        self.assertIn("passage-grounded adjudicator", client.calls[1][1])

    def test_direct_evidence_adjudicator_overrides_ambiguous_verified_answer(self) -> None:
        problem = self._ambiguous_deuteronomy_problem()
        client = FakeClient(["D", "D"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.strategy, "gemma_verified_direct_evidence")
        self.assertEqual(prediction.confidence, 0.74)
        self.assertEqual(prediction.trace[-1].role, "evidence-adjudicator")
        self.assertIn("direct passage evidence favored A", prediction.trace[-1].detail)

    def test_date_evidence_adjudicator_handles_flexible_date_formatting(self) -> None:
        problem = Problem(
            qid="test_date_evidence",
            question=(
                "Doan thong tin:\n"
                "Thinking Out Loud tro thanh bai hat dau tien dat 500 trieu streams "
                "vao ngay 12 thang 7, nam 2015. Bang xep hang sau do tiep tuc thay doi "
                "qua nhieu giai doan va nhieu nghe si khac nhau trong mot khoang thoi gian dai. "
                "Mot thang sau do, Thinking Out Loud "
                "bi Lean On soan ngoi cho den khi One Dance vuot qua vao ngay 18 thang 10 nam 2016.\n"
                "Cau hoi: Bai hat dat 500 trieu streams vao thoi diem nao?"
            ),
            choices=(
                "Ngay 12 thang 7 nam 2015",
                "Ngay 22 thang 2 nam 2015",
                "Ngay 18 thang 10 nam 2016",
                "Ngay 27 thang 10 nam 2013",
            ),
        )

        decision = adjudicate_date_evidence(problem, "C", self.config)

        self.assertIsNotNone(decision)
        self.assertEqual(decision.answer, "A")  # type: ignore[union-attr]
        self.assertIn("date passage evidence favored A", decision.detail)  # type: ignore[union-attr]

    def test_calculation_adjudicator_overrides_gdp_inflation_drift(self) -> None:
        problem = Problem(
            qid="test_gdp_inflation",
            question=(
                "Trong mot nam nhat dinh, GDP danh nghia cua mot quoc gia la 500 ty USD "
                "va GDP thuc te la 400 ty USD. Neu chi so gia GDP cua nam truoc la 100, "
                "thi ty le lam phat cho nam hien tai la bao nhieu?"
            ),
            choices=("20%", "25%", "30%", "15%"),
        )
        client = FakeClient(["A", "A"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "B")
        self.assertEqual(prediction.strategy, "gemma_verified_calculation")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("gdp inflation calculation favored B", prediction.trace[-1].detail)

    def test_calculation_adjudicator_overrides_cylinder_rate_repair(self) -> None:
        problem = Problem(
            qid="test_cylinder_rate",
            question=(
                "Một bể chứa hình trụ đang được đổ đầy nước với tốc độ không đổi là "
                "50 centimet khối mỗi giây. Khi độ cao của nước trong bể là 10 cm, "
                "bán kính của bể là 5 cm. Hỏi tốc độ tăng của độ cao nước là bao nhiêu?"
            ),
            choices=(
                "0.2 cm/giay",
                "0.4 cm/giay",
                "0.6 cm/giay",
                "0.8 cm/giay",
                "1.0 cm/giay",
                "1.2 cm/giay",
                "1.4 cm/giay",
                "1.6 cm/giay",
                "1.8 cm/giay",
                "2.0 cm/giay",
            ),
        )
        client = FakeClient(["The volume of a cylinder is V = pi r^2 h.", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "C")
        self.assertEqual(prediction.strategy, "gemma_repaired_calculation")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("cylinder fill rate calculation favored C", prediction.trace[-1].detail)

    def test_calculation_adjudicator_solves_buffer_ph(self) -> None:
        problem = Problem(
            qid="test_buffer_ph",
            question=(
                "Xét một dung dịch đệm gồm axit yếu HB và bazơ liên hợp B-. "
                "Giá trị pKa của HB là 5,00. Nếu nồng độ của HB là 0,2 M "
                "và nồng độ của B- là 0,1 M, thì giá trị pH là bao nhiêu?"
            ),
            choices=(
                "4,50",
                "4,75",
                "5,00",
                "5,25",
                "5,50",
            ),
        )
        client = FakeClient(["A", "A"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "B")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("buffer pH calculation favored B", prediction.trace[-1].detail)

    def test_calculation_adjudicator_solves_symbolic_cylinder_rate(self) -> None:
        problem = Problem(
            qid="test_symbolic_cylinder_rate",
            question=(
                "Mot be chua hinh tru dang duoc do day nuoc voi toc do 500 cm^3/sec. "
                "Ban kinh cua be la 10 cm. Hoi toc do tang cua chieu cao nuoc la bao nhieu?"
            ),
            choices=(
                r"$ \frac{1}{20\pi} $",
                r"$ \frac{1}{10\pi} $",
                r"$ \frac{1}{5\pi} $",
                r"$ \frac{1}{2\pi} $",
                r"$ \frac{1}{\pi} $",
                r"$ \frac{2}{\pi} $",
                r"$ \frac{5}{\pi} $",
            ),
        )
        client = FakeClient(["D", "D"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "G")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("cylinder fill rate calculation favored G", prediction.trace[-1].detail)

    def test_calculation_adjudicator_solves_carbon_percent_from_co2(self) -> None:
        problem = Problem(
            qid="test_carbon_percent",
            question=(
                "Khi dot 5g mot mau thep trong khi oxi thi thu duoc 0,1g khi CO2. "
                "Vay phan tram cacbon co chua trong thep la bao nhieu?"
            ),
            choices=("0,55%.", "5,45%.", "54,50%.", "10,90%."),
        )
        client = FakeClient(["B", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("carbon percent from CO2 calculation favored A", prediction.trace[-1].detail)

    def test_calculation_adjudicator_solves_wire_length(self) -> None:
        problem = Problem(
            qid="test_wire_length",
            question=(
                "Mot ban la dien co cong suat dinh muc 1100W va cuong do dong dien dinh muc 5A. "
                "Dien tro suat la rho = 1,1.10-6 ohm m va tiet dien cua day la S = 0,5mm2, "
                "chieu dai cua day dan la bao nhieu?"
            ),
            choices=("A.20m", "10m", "40m", "50m"),
        )
        client = FakeClient(["C", "C"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("wire length from power", prediction.trace[-1].detail)

    def test_calculation_adjudicator_solves_ideal_transformer_current(self) -> None:
        problem = Problem(
            qid="test_ideal_transformer",
            question=(
                "Mot bien ap ly tuong co cuon day so cap voi 1000 vong va cuon day thu cap voi 250 vong. "
                "Dong dien thu cap la 10 A. Dong dien so cap la bao nhieu?"
            ),
            choices=("2.5 A", "5 A", "7.5 A", "10 A"),
        )
        client = FakeClient(["B", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("ideal transformer primary current", prediction.trace[-1].detail)

    def test_calculation_adjudicator_solves_quadratic_production_maximum(self) -> None:
        problem = Problem(
            qid="test_quadratic_production",
            question=(
                "Trong ngan han, ham san xuat Q = 10L - 0.1L^2. "
                "So luong lao dong toi da de toi da hoa san luong la bao nhieu?"
            ),
            choices=("50", "100", "150", "200"),
        )
        client = FakeClient(["B", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            verify=True,
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")
        self.assertIn("quadratic production maximum labor", prediction.trace[-1].detail)

    def test_principle_adjudicator_uses_named_rule_registry(self) -> None:
        # Per-question principle hard-codes (preschool accreditation, Ho Chi Minh
        # communism adaptation, three-wire wattmeter, etc.) were removed as public-463
        # overfit / hard-coded answers. The registry must stay empty.
        self.assertEqual(list_principle_rules(), ())

    def test_tournament_repairs_invalid_variant_outputs(self) -> None:
        problem = Problem(
            qid="test_tournament_repair",
            question="Chon dap an dung nhat.",
            choices=("A one", "B two", "C three", "D four", "E five"),
        )
        client = FakeClient(
            [
                "I should explain this before answering.",
                "C",
                "C",
                "B",
            ]
        )

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            strategy="tournament",
            verify=False,
            config=self.config,
        )

        self.assertEqual(prediction.answer, "C")
        self.assertEqual(prediction.strategy, "gemma_tournament")
        self.assertIn("repair=C", prediction.raw_answer)
        self.assertEqual(prediction.trace[1].detail, "variant output repaired to a valid answer letter")

    def test_tournament_tie_uses_tiebreaker_before_verifier(self) -> None:
        problem = Problem(
            qid="test_tournament_tie",
            question="Chon dap an dung nhat.",
            choices=("A one", "B two", "C three", "D four", "E five"),
        )
        client = FakeClient(["A", "B", "C", "B", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            strategy="tournament",
            verify=False,
            config=self.config,
        )

        self.assertEqual(prediction.answer, "B")
        self.assertIn("tiebreak=B=>B", prediction.raw_answer)
        self.assertIn("verifier=B=>B", prediction.raw_answer)
        self.assertEqual(
            [step.role for step in prediction.trace],
            [
                "classifier",
                "solver",
                "solver",
                "solver",
                "synthesizer",
                "tie-breaker",
                "verifier",
            ],
        )
        self.assertEqual(prediction.trace[4].status, "warning")
        self.assertIn("tied=A,B,C", prediction.trace[4].detail)

    def test_tournament_applies_calculation_adjudicator(self) -> None:
        problem = Problem(
            qid="test_tournament_cylinder_rate",
            question=(
                "Một bể chứa hình trụ đang được đổ đầy nước với tốc độ không đổi là "
                "50 centimet khối mỗi giây. Khi độ cao của nước trong bể là 10 cm, "
                "bán kính của bể là 5 cm. Hỏi tốc độ tăng của độ cao nước là bao nhiêu?"
            ),
            choices=(
                "0.2 cm/giay",
                "0.4 cm/giay",
                "0.6 cm/giay",
                "0.8 cm/giay",
                "1.0 cm/giay",
            ),
        )
        client = FakeClient(["B", "B", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            strategy="tournament",
            verify=False,
            config=self.config,
        )

        self.assertEqual(prediction.answer, "C")
        self.assertEqual(prediction.trace[-1].role, "calculation-adjudicator")

    def test_tournament_applies_direct_evidence_adjudicator(self) -> None:
        problem = self._ambiguous_deuteronomy_problem()
        client = FakeClient(["D", "D"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            strategy="tournament",
            verify=False,
            config=self.config,
        )

        self.assertEqual(prediction.answer, "A")
        self.assertEqual(prediction.trace[-1].role, "evidence-adjudicator")

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

    def _ambiguous_deuteronomy_problem(self) -> Problem:
        question = (
            "Doan thong tin:\n"
            "1.1 Torah\n"
            "Noi loan chong lai cha me Deuteronomy 21:18-21.\n"
            "Quan he tinh duc giua mot nguoi dan ong va mot nguoi phu nu da dinh hon "
            "voi mot nguoi dan ong khac trong thi tran, vi co ay khong het len bao "
            "dong, Deuteronomy 22:23-24; ca hai nguoi nen bi nem da den chet.\n"
            "1.2 Mishna\n"
            "Mot nguoi da hanh hung mot co gai da hua hon; mot dua con trai buong "
            "binh va noi loan.\n"
            "Cau hoi: Theo noi dung duoc cung cap, trong cac toi danh sau day, "
            "toi nao duoc quy dinh trong Torah, cu the la Deuteronomy, la bi xu tu "
            "bang hinh thuc nem da?"
        )
        return Problem(
            qid="test_ambiguous_deuteronomy",
            question=question,
            choices=(
                "Quan he tinh duc voi mot nguoi phu nu da dinh hon voi nguoi khac ma khong co tieng keu cuu (Deuteronomy 22:23-24)",
                "Giao cau voi gia suc (duoc quy dinh trong Mishna)",
                "Nguyen rua cha hoac me (duoc quy dinh trong Mishna)",
                "Con trai buong binh va noi loan (Deuteronomy 21:18-21)",
            ),
        )

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

    def test_verifier_repairs_invalid_output_before_keep_or_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_verifier_repair",
                            "question": "Question: choose one.",
                            "choices": ["A choice", "B choice", "C choice", "D choice"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]
            client = FakeClient(["A", "I need to explain instead of returning a letter.", "B"])

        prediction = solve_problem(
            problem,
            client,  # type: ignore[arg-type]
            strategy="verify",
            config=self.config,
        )

        self.assertEqual(prediction.answer, "B")
        self.assertEqual(prediction.strategy, "gemma_verified")
        self.assertIn("verifier_repair=B", prediction.raw_answer)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual([step.role for step in prediction.trace], ["classifier", "solver", "verifier"])
        self.assertEqual(
            prediction.trace[-1].detail,
            "verifier output repaired to a valid answer letter",
        )

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

    def test_trace_review_reports_prediction_risk_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "test_risk",
                            "question": "Tinh 2 + 2 bang bao nhieu?",
                            "choices": ["0", "1", "2", "3", "4"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]
            prediction = Prediction(
                qid=problem.qid,
                answer="B",
                model="fake/gemma-4",
                raw_answer="A|B",
                strategy="gemma_tournament",
                confidence=0.72,
                trace=(
                    TraceStep(
                        "classifier",
                        "profile_problem",
                        "completed",
                        (
                            "kind=calculation; variant=calculation; verify=True; "
                            "tournament=True; features=has_many_choices,has_calculation; "
                            "diagnostics=ignored_calculation_marker=tinh"
                        ),
                    ),
                    TraceStep("solver", "tournament:direct", "completed", "ok", "A"),
                    TraceStep("solver", "tournament:evidence", "completed", "ok", "B"),
                    TraceStep(
                        "synthesizer",
                        "majority_vote",
                        "warning",
                        "votes=1/2; distribution=A:1,B:1; tied=A,B",
                        "A",
                    ),
                    TraceStep("tie-breaker", "answer_only_check", "completed", "ok", "B"),
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
                    workflow="risk-review-test",
                    strategy="tournament",
                    dry_run=False,
                    verify=True,
                    model="fake/gemma-4",
                    limit=1,
                    summary=summary,
                    argv=("--strategy", "tournament"),
                ),
            )

            review = review_trace_dir(trace_dir)
            codes = {finding.code for finding in review.findings}

        self.assertEqual(review.verdict, "warn")
        self.assertIn("risk_agent_disagreement", codes)
        self.assertIn("risk_tournament_tie", codes)
        self.assertIn("risk_broad_marker_ignored", codes)
        self.assertIn("risk_compound_many_choice_calculation", codes)

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
