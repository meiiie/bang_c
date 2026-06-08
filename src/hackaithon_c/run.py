from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .evaluation import validate_predictions, write_summary
from .exporter import write_predictions, write_trace
from .loader import find_input_file, load_problems
from .nvidia_client import NvidiaChatClient, NvidiaConfig
from .solver import solve_problem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HackAIthon 2026 Bang C runner")
    parser.add_argument("--config", default=None, help="Harness config JSON path")
    parser.add_argument("--data-dir", default="/data", help="Contest input directory")
    parser.add_argument("--output-dir", default="/output", help="Contest output directory")
    parser.add_argument("--input", default=None, help="Explicit input JSON/CSV for local dev")
    parser.add_argument("--limit", type=int, default=None, help="Optional local dev limit")
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
    input_path = Path(args.input) if args.input else find_input_file(Path(args.data_dir), config)
    output_dir = Path(args.output_dir)
    output_path = output_dir / config.output_file

    problems = load_problems(input_path)
    if args.limit is not None:
        problems = problems[: args.limit]

    client = None
    if not args.dry_run:
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
            dry_run=args.dry_run,
            verify=args.verify,
            strategy=args.strategy or config.default_strategy,
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
