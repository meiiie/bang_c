from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .branding import render_banner, version_line
from .capabilities import collect_capabilities, render_capabilities
from .config import load_config
from .doctor import collect_doctor_checks, render_doctor_report
from .evaluation import validate_predictions, write_summary
from .exporter import write_predictions, write_trace
from .loader import find_input_file, load_problems
from .nvidia_client import NvidiaChatClient, NvidiaConfig
from .solver import solve_problem
from .workflows import list_workflows, render_workflows, resolve_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neko Core inference harness")
    parser.add_argument("--config", default=None, help="Harness config JSON path")
    parser.add_argument("--data-dir", default="/data", help="Contest input directory")
    parser.add_argument("--output-dir", default="/output", help="Contest output directory")
    parser.add_argument("--input", default=None, help="Explicit input JSON/CSV for local dev")
    parser.add_argument("--limit", type=int, default=None, help="Optional local dev limit")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--doctor", action="store_true", help="Run environment and contract diagnostics")
    parser.add_argument("--capabilities", action="store_true", help="Print harness capability registry")
    parser.add_argument("--list-workflows", action="store_true", help="Print configured workflows")
    parser.add_argument("--workflow", default=None, help="Run a configured workflow by name")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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

    if args.list_workflows:
        print(render_workflows(list_workflows(config)))
        return 0

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
    output_dir = Path(args.output_dir)
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
        trace_enabled=bool(args.trace_dir),
    )
    if not summary.valid:
        messages = "; ".join(issue.code for issue in summary.issues[:5])
        raise RuntimeError(f"Invalid prediction contract: {messages}")

    write_predictions(output_path, predictions)
    if args.trace_dir:
        trace_dir = Path(args.trace_dir)
        write_trace(trace_dir, predictions)
        write_summary(trace_dir / "run-summary.json", summary)

    print(f"Loaded {len(problems)} problems from {input_path}")
    if workflow is not None:
        print(f"Workflow: {workflow.name}")
    print(f"Wrote predictions to {output_path}")
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
