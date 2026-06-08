from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .branding import render_banner, version_line
from .capabilities import collect_capabilities, render_capabilities
from .compare import compare_trace_dirs, render_trace_comparison
from .config import load_config
from .doctor import collect_doctor_checks, render_doctor_report
from .evaluation import validate_predictions, write_summary
from .exporter import write_predictions, write_trace
from .loader import find_input_file, load_problems
from .manifest import build_run_manifest, write_run_manifest
from .model_inventory import collect_model_inventory, render_model_inventory
from .nvidia_client import NvidiaChatClient, NvidiaConfig
from .project import init_project
from .review import render_trace_review, review_trace_dir
from .review_tasks import (
    build_review_tasks,
    render_review_tasks,
    write_review_tasks_json,
    write_review_tasks_markdown,
)
from .session import prepare_run_session, write_run_report
from .solver import solve_problem
from .workflows import list_workflows, render_workflows, resolve_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neko Core inference harness")
    parser.add_argument("--config", default=None, help="Harness config JSON path")
    parser.add_argument("--data-dir", default="/data", help="Contest input directory")
    parser.add_argument("--output-dir", default=None, help="Contest output directory")
    parser.add_argument("--input", default=None, help="Explicit input JSON/CSV for local dev")
    parser.add_argument("--limit", type=int, default=None, help="Optional local dev limit")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--init", action="store_true", help="Create a project-local .neko-core/config.json")
    parser.add_argument("--force", action="store_true", help="Overwrite files for commands that support it")
    parser.add_argument("--doctor", action="store_true", help="Run environment and contract diagnostics")
    parser.add_argument("--capabilities", action="store_true", help="Print harness capability registry")
    parser.add_argument("--model-inventory", action="store_true", help="Probe provider models and Bang C eligibility")
    parser.add_argument("--list-workflows", action="store_true", help="Print configured workflows")
    parser.add_argument("--workflow", default=None, help="Run a configured workflow by name")
    parser.add_argument("--review-trace", default=None, help="Review an existing dev trace directory")
    parser.add_argument("--review-tasks", default=None, help="Create reviewer task queue from a trace directory")
    parser.add_argument(
        "--compare-traces",
        nargs=2,
        metavar=("LEFT", "RIGHT"),
        help="Compare two existing dev trace directories",
    )
    parser.add_argument("--banner", action="store_true", help="Print the ASCII Neko Core banner")
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic heuristic only")
    parser.add_argument(
        "--strategy",
        choices=("auto", "direct", "verify", "tournament"),
        default=None,
        help="Solving strategy",
    )
    parser.add_argument("--verify", action="store_true", help="Force a second Gemma pass when supported")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first model/API error")
    parser.add_argument("--trace-dir", default=None, help="Optional dev trace directory")
    parser.add_argument("--run-dir", default=None, help="Create a local run session with output, traces, and report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.init:
        result = init_project(Path.cwd(), force=args.force)
        print(result.message)
        return 0

    config = load_config(args.config)

    if args.version:
        print(version_line(config))
        return 0

    if args.banner:
        print(render_banner(config))
        return 0

    if args.capabilities:
        print(render_capabilities(collect_capabilities(config)))
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

    if args.compare_traces:
        comparison = compare_trace_dirs(
            Path(args.compare_traces[0]),
            Path(args.compare_traces[1]),
        )
        print(render_trace_comparison(comparison))
        return 1 if comparison.verdict == "fail" else 0

    if args.doctor:
        input_path = Path(args.input) if args.input else None
        checks = collect_doctor_checks(config, data_dir=Path(args.data_dir), input_path=input_path)
        print(render_doctor_report(checks))
        return 0

    try:
        workflow = resolve_workflow(config, args.workflow)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    dry_run = args.dry_run or bool(workflow and workflow.dry_run)
    verify = args.verify or bool(workflow and workflow.verify)
    strategy = args.strategy or (workflow.strategy if workflow else config.default_strategy)

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

    problems = load_problems(input_path)
    if args.limit is not None:
        problems = problems[: args.limit]

    client = None
    if not dry_run:
        client = NvidiaChatClient(
            NvidiaConfig.from_env(
                default_base_url=config.base_url,
                default_model=config.default_model,
                default_timeout_seconds=config.timeout_seconds,
                default_max_retries=config.max_retries,
            )
        )

    predictions = [
        solve_problem(
            problem,
            client,
            dry_run=dry_run,
            verify=verify,
            strategy=strategy,
            fail_fast=args.fail_fast,
            config=config,
        )
        for problem in problems
    ]
    summary = validate_predictions(
        problems,
        predictions,
        config,
        trace_enabled=bool(trace_dir),
    )
    if not summary.valid:
        messages = "; ".join(issue.code for issue in summary.issues[:5])
        raise RuntimeError(f"Invalid prediction contract: {messages}")

    write_predictions(output_path, predictions)
    if trace_dir:
        write_trace(trace_dir, predictions)
        write_summary(trace_dir / "run-summary.json", summary)
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

    print(f"Loaded {len(problems)} problems from {input_path}")
    if workflow is not None:
        print(f"Workflow: {workflow.name}")
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


if __name__ == "__main__":
    raise SystemExit(main())
