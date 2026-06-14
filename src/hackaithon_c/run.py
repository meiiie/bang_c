from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agents import list_agents, render_agent_detail, render_agents, resolve_agent
from .branding import render_banner, render_quickstart, version_line
from .capabilities import collect_capabilities, render_capabilities
from .checkpoint import (
    append_checkpoint,
    clear_checkpoint,
    checkpoint_meta_path,
    load_checkpoint,
    verify_checkpoint_meta,
    write_checkpoint,
    write_checkpoint_meta,
)
from .command_registry import (
    list_commands,
    render_command_detail,
    render_commands,
    resolve_command,
)
from .compare import compare_trace_dirs, render_trace_comparison
from .config import load_config
from .doctor import collect_doctor_checks, render_doctor_report
from .evaluation import (
    repair_predictions_for_contract,
    validate_predictions,
    write_summary,
)
from .events import build_event, load_events, render_events, write_events
from .exporter import write_predictions, write_trace
from .loader import filter_problems_by_qids, find_input_file, load_problems
from .manifest import build_run_manifest, write_run_manifest
from .model_client import build_challenger_client, build_chat_client, effective_provider
from .model_inventory import classify_model, collect_model_inventory, render_model_inventory
from .policy import evaluate_policy, render_policy_report
from .project import init_project, init_user_config
from .review import render_trace_review, review_trace_dir
from .review_tasks import (
    build_review_tasks,
    render_review_tasks,
    write_review_tasks_json,
    write_review_tasks_markdown,
)
from .session import (
    discover_run_sessions,
    load_run_session_record,
    prepare_run_session,
    render_run_session_detail,
    render_run_sessions,
    write_run_report,
)
from .solver import solve_problem
from .submission import check_submission_file, render_submission_check
from .tool_registry import list_tools, render_tool_detail, render_tools, resolve_tool
from .workflows import list_workflows, render_workflows, resolve_workflow


def parse_args(argv: tuple[str, ...] | None = None) -> argparse.Namespace:
    normalized_argv = _normalize_cli_argv(tuple(sys.argv[1:] if argv is None else argv))
    parser = argparse.ArgumentParser(description="Neko Core inference harness")
    parser.add_argument("--config", default=None, help="Harness config JSON path")
    parser.add_argument("--profile", default=None, help="Named runtime profile from config")
    parser.add_argument("--data-dir", default="/data", help="Contest input directory")
    parser.add_argument("--output-dir", default=None, help="Contest output directory")
    parser.add_argument("--input", default=None, help="Explicit input JSON/CSV for local dev")
    parser.add_argument("--qid", action="append", default=[], help="Run only this qid; repeat for multiple qids")
    parser.add_argument("--limit", type=int, default=None, help="Optional local dev limit")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--init", action="store_true", help="Create a project-local .neko-core/config.json")
    parser.add_argument("--init-user", dest="init_user", action="store_true", help="Create a user-level ~/.neko-core/config.json (for API key + provider, like claude.json)")
    parser.add_argument("--force", action="store_true", help="Overwrite files for commands that support it")
    parser.add_argument("--doctor", action="store_true", help="Run environment and contract diagnostics")
    parser.add_argument("--capabilities", action="store_true", help="Print harness capability registry")
    parser.add_argument("--agents", action="store_true", help="Print harness agent role registry")
    parser.add_argument("--agent", default=None, help="Print one harness agent role")
    parser.add_argument("--tools", action="store_true", help="Print harness tool registry")
    parser.add_argument("--tool", default=None, help="Print one harness tool contract")
    parser.add_argument("--commands", action="store_true", help="Print harness command registry")
    parser.add_argument("--command", default=None, help="Print one harness command contract")
    parser.add_argument("--policy", action="store_true", help="Audit harness runtime/development policy")
    parser.add_argument("--model-inventory", action="store_true", help="Probe provider models and Bang C eligibility")
    parser.add_argument("--profiles", action="store_true", help="Print configured runtime profiles")
    parser.add_argument(
        "--provider",
        choices=("local_llamacpp", "nvidia", "local_server"),
        default=None,
        help="Runtime model provider. Defaults to config/env.",
    )
    parser.add_argument("--list-workflows", action="store_true", help="Print configured workflows")
    parser.add_argument("--workflow", default=None, help="Run a configured workflow by name")
    parser.add_argument(
        "--allow-development-workflow",
        action="store_true",
        help=(
            "Explicitly allow non-dry-run development workflows/strategies. "
            "Never use this in the final Docker runtime path."
        ),
    )
    parser.add_argument("--review-trace", default=None, help="Review an existing dev trace directory")
    parser.add_argument("--review-tasks", default=None, help="Create reviewer task queue from a trace directory")
    parser.add_argument("--check-submission", default=None, help="Validate a pred.csv artifact against the input contract")
    parser.add_argument("--list-runs", action="store_true", help="List local run sessions")
    parser.add_argument("--runs-root", default=".", help="Root directory for --list-runs")
    parser.add_argument("--session", default=None, help="Show details for a local run session")
    parser.add_argument("--events", default=None, help="Show a run session event log")
    parser.add_argument(
        "--compare-traces",
        nargs=2,
        metavar=("LEFT", "RIGHT"),
        help="Compare two existing dev trace directories",
    )
    parser.add_argument(
        "--compare-qid",
        action="append",
        default=[],
        help="Limit --compare-traces to this qid; repeat for multiple qids",
    )
    parser.add_argument("--banner", action="store_true", help="Print the ASCII Neko Core banner")
    parser.add_argument("--quickstart", action="store_true", help="Print a short command guide and exit")
    parser.add_argument(
        "--yolo",
        action="store_true",
        help=(
            "Run the bounded autonomous contest preset: contest-strict, "
            "auto-resume, checkpointing, trace review, and policy enforcement."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic heuristic only")
    parser.add_argument(
        "--strategy",
        choices=("auto", "direct", "verify", "tournament", "self_consistency", "tiered"),
        default=None,
        help="Solving strategy",
    )
    parser.add_argument("--verify", action="store_true", help="Force a second Gemma pass when supported")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first model/API error")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Solve this many questions concurrently. Needs an HTTP provider "
            "(local_server or nvidia); the in-process llama.cpp client is "
            "single-threaded, so workers is forced to 1 there."
        ),
    )
    parser.add_argument("--trace-dir", default=None, help="Optional dev trace directory")
    parser.add_argument("--run-dir", default=None, help="Create a local run session with output, traces, and report")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse qid predictions from an existing run-dir/trace-dir checkpoint",
    )
    parser.add_argument(
        "--auto-resume",
        action="store_true",
        help="Automatically reuse a compatible checkpoint when one exists; stale checkpoints are cleared.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="Flush trace checkpoint after this many newly solved items; 0 disables checkpointing",
    )
    return parser.parse_args(normalized_argv)


def apply_yolo_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if not args.yolo:
        return args
    if args.workflow is None:
        args.workflow = "contest-strict"
    args.auto_resume = True
    if args.checkpoint_every == 0:
        args.checkpoint_every = 1
    if args.run_dir is None and args.trace_dir is None:
        if args.input is None and Path(args.data_dir).as_posix() == "/data":
            args.output_dir = args.output_dir or "/output"
            args.run_dir = "/output/neko-run"
        else:
            args.run_dir = "run-yolo"
    return args


def main(argv: tuple[str, ...] | None = None) -> int:
    raw_argv = tuple(sys.argv[1:] if argv is None else argv)
    args = apply_yolo_defaults(parse_args(raw_argv))

    if args.init:
        result = init_project(Path.cwd(), force=args.force)
        print(result.message)
        return 0

    if args.init_user:
        result = init_user_config(force=args.force)
        print(result.message)
        return 0

    try:
        config = load_config(args.config, profile=args.profile)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.version:
        print(version_line(config))
        return 0

    if args.banner:
        print(render_banner(config))
        return 0

    if args.quickstart or not _normalize_cli_argv(raw_argv):
        print(render_quickstart(config))
        return 0

    if args.capabilities:
        print(render_capabilities(collect_capabilities(config)))
        return 0

    if args.agents:
        print(render_agents(list_agents(config)))
        return 0

    if args.agent:
        try:
            print(render_agent_detail(resolve_agent(config, args.agent)))
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        return 0

    if args.tools:
        print(render_tools(list_tools(config)))
        return 0

    if args.tool:
        try:
            print(render_tool_detail(resolve_tool(config, args.tool)))
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        return 0

    if args.commands:
        print(render_commands(list_commands(config)))
        return 0

    if args.command:
        try:
            print(render_command_detail(resolve_command(config, args.command)))
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        return 0

    if args.policy:
        report = evaluate_policy(config)
        print(render_policy_report(report))
        return 1 if report.verdict == "fail" else 0

    if args.profiles:
        print(render_runtime_profiles(config))
        return 0

    if args.model_inventory:
        report = collect_model_inventory(config)
        rendered = render_model_inventory(report)
        if args.run_dir:
            report_path = Path(args.run_dir) / "model-inventory.txt"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(rendered + "\n", encoding="utf-8")
            print(f"Model inventory report: {report_path}")
        print(rendered)
        return 1 if report.status == "fail" else 0

    if args.list_workflows:
        print(render_workflows(list_workflows(config)))
        return 0

    if args.review_trace:
        review = review_trace_dir(Path(args.review_trace))
        print(render_trace_review(review))
        return 1 if review.verdict == "fail" else 0

    if args.review_tasks:
        review = review_trace_dir(Path(args.review_tasks))
        tasks = build_review_tasks(review)
        rendered = render_review_tasks(tasks)
        if args.run_dir:
            session = prepare_run_session(Path(args.run_dir))
            write_review_tasks_json(session.review_tasks_json_path, tasks)
            write_review_tasks_markdown(session.review_tasks_markdown_path, tasks)
            print(f"Review tasks: {session.review_tasks_markdown_path}")
        print(rendered)
        return 1 if review.verdict == "fail" else 0

    if args.check_submission:
        try:
            input_path = Path(args.input) if args.input else find_input_file(Path(args.data_dir), config)
            problems = load_problems(input_path)
            check = check_submission_file(Path(args.check_submission), problems, config)
        except (FileNotFoundError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        print(render_submission_check(check))
        return 0 if check.valid else 1

    if args.list_runs:
        root = Path(args.runs_root)
        print(render_run_sessions(discover_run_sessions(root), root=root))
        return 0

    if args.session:
        record = load_run_session_record(Path(args.session))
        if record is None:
            print(f"Error: run session not found: {args.session}", file=sys.stderr)
            return 2
        print(render_run_session_detail(record))
        return 0

    if args.events:
        source = Path(args.events)
        print(render_events(load_events(source), source=source))
        return 0

    if args.compare_traces:
        comparison = compare_trace_dirs(
            Path(args.compare_traces[0]),
            Path(args.compare_traces[1]),
            qids=tuple(args.compare_qid),
        )
        print(render_trace_comparison(comparison))
        return 1 if comparison.verdict == "fail" else 0

    if args.doctor:
        input_path = Path(args.input) if args.input else None
        checks = collect_doctor_checks(
            config,
            data_dir=Path(args.data_dir),
            input_path=input_path,
            provider=args.provider,
        )
        print(render_doctor_report(checks))
        return 0

    policy_report = evaluate_policy(config)
    if policy_report.verdict == "fail":
        print(render_policy_report(policy_report), file=sys.stderr)
        return 1

    try:
        workflow = resolve_workflow(config, args.workflow)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    dry_run = args.dry_run or bool(workflow and workflow.dry_run)
    verify = args.verify or bool(workflow and workflow.verify)
    strategy = args.strategy or (workflow.strategy if workflow else config.default_strategy)
    if not dry_run and _requires_development_workflow_allow(config, workflow, strategy):
        if not _development_workflow_allowed(args):
            print(
                "Error: non-dry-run development workflow/strategy requires "
                "--allow-development-workflow or HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1",
                file=sys.stderr,
            )
            return 2

    input_path = Path(args.input) if args.input else find_input_file(Path(args.data_dir), config)
    run_session = None
    trace_dir = Path(args.trace_dir) if args.trace_dir else None
    if args.run_dir:
        run_session = prepare_run_session(
            Path(args.run_dir),
            output_dir=Path(args.output_dir) if args.output_dir else None,
            trace_dir=trace_dir,
        )
        output_dir = run_session.output_dir
        trace_dir = run_session.trace_dir
    else:
        output_dir = Path(args.output_dir or "/output")
    output_path = output_dir / config.output_file

    if (args.resume or args.auto_resume) and trace_dir is None:
        print("Error: --resume/--auto-resume requires --run-dir or --trace-dir", file=sys.stderr)
        return 2
    if args.checkpoint_every < 0:
        print("Error: --checkpoint-every must be >= 0", file=sys.stderr)
        return 2

    problems = load_problems(input_path)
    if args.qid:
        problems = filter_problems_by_qids(problems, tuple(args.qid))
    if args.limit is not None:
        problems = problems[: args.limit]

    client = None
    challenger = None
    if not dry_run:
        try:
            client = build_chat_client(config, provider=args.provider)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        try:
            validate_runtime_model(client.model, config)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        try:
            challenger = build_challenger_client(config)
            if challenger is not None:
                # The contest model-family allowlist applies to the second model too.
                validate_runtime_model(challenger.model, config)
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2

    resumed_predictions = {}
    checkpoint_enabled = trace_dir is not None and args.checkpoint_every > 0
    if trace_dir is not None:
        auto_resume_checkpoint = args.auto_resume and checkpoint_meta_path(trace_dir).exists()
        if args.resume or auto_resume_checkpoint:
            try:
                verify_checkpoint_meta(
                    trace_dir,
                    config=config,
                    input_path=input_path,
                    workflow=workflow.name if workflow else None,
                    strategy=strategy,
                    dry_run=dry_run,
                    verify=verify,
                    model=client.model if client else "heuristic",
                    total_problems=len(problems),
                )
            except ValueError as error:
                if args.resume:
                    print(f"Error: {error}", file=sys.stderr)
                    return 2
                clear_checkpoint(trace_dir)
                resumed_predictions = {}
            else:
                resumed_predictions = load_checkpoint(trace_dir)
        else:
            clear_checkpoint(trace_dir)
        if checkpoint_enabled:
            write_checkpoint_meta(
                trace_dir,
                config=config,
                input_path=input_path,
                workflow=workflow.name if workflow else None,
                strategy=strategy,
                dry_run=dry_run,
                verify=verify,
                model=client.model if client else "heuristic",
                total_problems=len(problems),
            )

    events = []
    if run_session is not None:
        events.append(
            build_event(
                "session_started",
                "started",
                "Run session started.",
                payload={
                    "workflow": workflow.name if workflow else None,
                    "provider": effective_provider(config, args.provider),
                    "strategy": strategy,
                    "dry_run": dry_run,
                    "verify": verify,
                    "input": str(input_path),
                    "output": str(output_path),
                    "total_problems": len(problems),
                    "resume": args.resume,
                    "auto_resume": args.auto_resume,
                    "yolo": args.yolo,
                    "resumed_predictions": len(resumed_predictions),
                    "checkpoint_every": args.checkpoint_every,
                },
            )
        )

    workers = max(1, args.workers)
    if workers > 1 and not dry_run:
        provider_name = effective_provider(config, args.provider)
        if provider_name == "local_llamacpp":
            print(
                "Warning: --workers > 1 needs an HTTP provider (local_server or "
                "nvidia); the in-process llama.cpp client is single-threaded. "
                "Falling back to workers=1.",
                file=sys.stderr,
            )
            workers = 1

    predictions = []
    pending_checkpoint = []
    unsolved = [
        problem for problem in problems if resumed_predictions.get(problem.qid) is None
    ]

    def _work(problem):
        return _solve_with_retry(
            problem,
            client,
            dry_run=dry_run,
            verify=verify,
            strategy=strategy,
            fail_fast=args.fail_fast,
            config=config,
            challenger=challenger,
        )

    # Results stream in input order either way, so checkpoint cadence, events, and
    # pred.csv ordering are identical between sequential and pooled execution.
    executor = ThreadPoolExecutor(max_workers=workers) if workers > 1 and unsolved else None
    result_iter = executor.map(_work, unsolved) if executor else (_work(p) for p in unsolved)
    try:
        for problem in problems:
            resumed = resumed_predictions.get(problem.qid)
            if resumed is not None:
                predictions.append(resumed)
                if run_session is not None:
                    events.append(
                        build_event(
                            "prediction_resumed",
                            "completed",
                            "Reused prediction from checkpoint.",
                            qid=resumed.qid,
                            payload={
                                "answer": resumed.answer,
                                "strategy": resumed.strategy,
                                "confidence": resumed.confidence,
                            },
                        )
                    )
                continue
            prediction, retry_infos = next(result_iter)
            if run_session is not None:
                for retry_info in retry_infos:
                    events.append(
                        build_event(
                            "prediction_retry_scheduled",
                            "warning",
                            "Retrying a transient fallback prediction.",
                            qid=prediction.qid,
                            payload=retry_info,
                        )
                    )
            predictions.append(prediction)
            if checkpoint_enabled:
                pending_checkpoint.append(prediction)
                if len(pending_checkpoint) >= args.checkpoint_every:
                    append_checkpoint(trace_dir, pending_checkpoint)
                    pending_checkpoint = []
            if run_session is not None:
                events.append(
                    build_event(
                        "prediction_completed",
                        "completed",
                        f"Predicted {prediction.answer} with {prediction.strategy}.",
                        qid=prediction.qid,
                        payload={
                            "answer": prediction.answer,
                            "strategy": prediction.strategy,
                            "confidence": prediction.confidence,
                            "question_kind": prediction.question_kind,
                            "fallback": bool(prediction.fallback_reason),
                        },
                    )
                )
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
    if checkpoint_enabled and pending_checkpoint:
        append_checkpoint(trace_dir, pending_checkpoint)

    # Bulletproof contract: guarantee a pred.csv covering exactly the input qids,
    # each with a valid letter, and WRITE IT BEFORE anything that could raise. A
    # partial/imperfect submission still scores; a missing /output/pred.csv scores
    # zero. The repair keeps good predictions verbatim (accuracy is never lowered).
    predictions = repair_predictions_for_contract(problems, predictions)
    write_predictions(output_path, predictions)

    summary = validate_predictions(
        problems,
        predictions,
        config,
        trace_enabled=bool(trace_dir),
    )
    if not summary.valid:
        messages = "; ".join(issue.code for issue in summary.issues[:5])
        print(
            f"Warning: prediction contract issues remain after repair: {messages}",
            file=sys.stderr,
        )
    if run_session is not None:
        events.append(
            build_event(
                "predictions_written",
                "completed",
                "Prediction CSV written.",
                payload={
                    "output": str(output_path),
                    "total_predictions": summary.total_predictions,
                    "valid": summary.valid,
                },
            )
        )
    if trace_dir:
        write_checkpoint(trace_dir, predictions)
        write_trace(trace_dir, predictions)
        write_summary(trace_dir / "run-summary.json", summary)
        if run_session is not None:
            events.append(
                build_event(
                    "trace_written",
                    "completed",
                    "Trace artifacts written.",
                    payload={"trace_dir": str(trace_dir)},
                )
            )
        write_run_manifest(
            trace_dir / "run-manifest.json",
            build_run_manifest(
                config=config,
                input_path=input_path,
                output_path=output_path,
                trace_dir=trace_dir,
                workflow=workflow.name if workflow else None,
                strategy=strategy,
                dry_run=dry_run,
                verify=verify,
                model=client.model if client else "heuristic",
                limit=args.limit,
                summary=summary,
                argv=tuple(sys.argv[1:]),
            ),
        )
        if run_session is not None:
            review = review_trace_dir(trace_dir)
            tasks = build_review_tasks(review)
            write_review_tasks_json(run_session.review_tasks_json_path, tasks)
            write_review_tasks_markdown(run_session.review_tasks_markdown_path, tasks)
            events.append(
                build_event(
                    "review_completed",
                    "completed" if review.verdict == "pass" else "warning",
                    f"Trace review finished with {review.verdict.upper()}.",
                    payload={
                        "verdict": review.verdict,
                        "findings": len(review.findings),
                        "review_tasks": len(tasks),
                    },
                )
            )
            write_run_report(
                run_session.report_path,
                input_path=input_path,
                output_path=output_path,
                trace_dir=trace_dir,
                workflow=workflow.name if workflow else None,
                strategy=strategy,
                dry_run=dry_run,
                verify=verify,
                model=client.model if client else "heuristic",
                summary=summary,
                review=review,
                review_tasks_path=run_session.review_tasks_markdown_path,
            )
            events.append(
                build_event(
                    "session_completed",
                    "completed",
                    "Run session completed.",
                    payload={
                        "run_report": str(run_session.report_path),
                        "events": str(run_session.events_path),
                    },
                )
            )
            write_events(run_session.events_path, tuple(events))

    print(f"Loaded {len(problems)} problems from {input_path}")
    if workflow is not None:
        print(f"Workflow: {workflow.name}")
    if args.yolo:
        print("YOLO mode: bounded autonomous run with policy enforcement, checkpointing, and review artifacts.")
    print(f"Wrote predictions to {output_path}")
    if run_session is not None:
        print(f"Run report: {run_session.report_path}")
    print(
        "Summary: "
        f"valid={summary.valid} "
        f"strategies={summary.strategies} "
        f"kinds={summary.question_kinds} "
        f"fallbacks={summary.fallbacks} "
        f"avg_confidence={summary.average_confidence} "
        f"harness_score={summary.harness_score}"
    )
    return 0


def validate_runtime_model(model_id: str, config) -> None:
    selected = classify_model(
        model_id,
        allowed_llm_families=config.allowed_model_families,
        allowed_embedding_families=config.allowed_embedding_families,
    )
    if selected.allowed and selected.category == "llm":
        return
    raise ValueError(
        "Runtime model is not allowed by Bang C rules: "
        f"{model_id} ({selected.reason}). "
        "Use a Gemma-4 model or a Qwen3.5 model with size <= 9B."
    )


def render_runtime_profiles(config) -> str:
    lines = ["Neko Core runtime profiles"]
    profiles = config.runtime_profiles
    if not profiles:
        lines.append("- none")
        return "\n".join(lines)
    for name, profile in profiles.items():
        marker = " (active)" if name == config.active_profile else ""
        provider = profile.get("provider", config.provider)
        model = profile.get("default_model", config.default_model)
        lines.append(f"- {name}{marker}: provider={provider}, model={model}")
    return "\n".join(lines)


def _development_workflow_allowed(args: argparse.Namespace) -> bool:
    if bool(getattr(args, "allow_development_workflow", False)):
        return True
    return os.environ.get("HACKC_ALLOW_DEVELOPMENT_WORKFLOW", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _requires_development_workflow_allow(config, workflow, strategy: str) -> bool:
    if workflow is not None and workflow.phase == "development":
        return True
    runtime_strategies = {
        item.strategy
        for item in list_workflows(config)
        if item.phase == "runtime"
    }
    development_strategies = {
        item.strategy
        for item in list_workflows(config)
        if item.phase == "development"
    }
    return strategy in (development_strategies - runtime_strategies)


def _is_retryable_prediction(prediction) -> bool:
    if prediction.fallback_reason is None:
        return False
    if prediction.strategy.endswith("_after_error"):
        return True
    return prediction.fallback_reason in {
        "RuntimeError",
        "ConnectionError",
        "Timeout",
        "ReadTimeout",
        "ConnectTimeout",
        "HTTPError",
    }


def _problem_retry_delay_seconds(attempt: int, config) -> float:
    delay = config.problem_retry_base_delay_seconds * (2**attempt)
    return min(config.problem_retry_max_delay_seconds, delay)


def _solve_with_retry(
    problem,
    client,
    *,
    dry_run,
    verify,
    strategy,
    fail_fast,
    config,
    challenger=None,
):
    """Solve one problem with the transient-fallback retry loop.

    Returns (prediction, retry_infos) where retry_infos carries the payloads for
    `prediction_retry_scheduled` events — emitted by the caller on the main
    thread, so this function is safe to run inside a worker pool.
    """
    prediction = solve_problem(
        problem,
        client,
        dry_run=dry_run,
        verify=verify,
        strategy=strategy,
        fail_fast=fail_fast,
        config=config,
        challenger=challenger,
    )
    retry_infos: list[dict] = []
    problem_retry = 0
    while (
        _is_retryable_prediction(prediction)
        and problem_retry < config.problem_max_retries
    ):
        delay_seconds = _problem_retry_delay_seconds(problem_retry, config)
        retry_infos.append(
            {
                "fallback_reason": prediction.fallback_reason,
                "attempt": problem_retry + 1,
                "delay_seconds": delay_seconds,
            }
        )
        time.sleep(delay_seconds)
        problem_retry += 1
        prediction = solve_problem(
            problem,
            client,
            dry_run=dry_run,
            verify=verify,
            strategy=strategy,
            fail_fast=fail_fast,
            config=config,
            challenger=challenger,
        )
    return prediction, retry_infos


def _normalize_cli_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    if argv and argv[0].lower() == "core":
        return argv[1:]
    return argv


if __name__ == "__main__":
    raise SystemExit(main())
