from __future__ import annotations

import argparse
from pathlib import Path

from .exporter import write_predictions, write_trace
from .loader import find_input_file, load_problems
from .nvidia_client import NvidiaChatClient, NvidiaConfig
from .solver import solve_problem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HackAIthon 2026 Bang C runner")
    parser.add_argument("--data-dir", default="/data", help="Contest input directory")
    parser.add_argument("--output-dir", default="/output", help="Contest output directory")
    parser.add_argument("--input", default=None, help="Explicit input JSON/CSV for local dev")
    parser.add_argument("--limit", type=int, default=None, help="Optional local dev limit")
    parser.add_argument("--dry-run", action="store_true", help="Use deterministic heuristic only")
    parser.add_argument("--verify", action="store_true", help="Use a second Gemma pass to verify each answer")
    parser.add_argument("--trace-dir", default=None, help="Optional dev trace directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input) if args.input else find_input_file(Path(args.data_dir))
    output_dir = Path(args.output_dir)
    output_path = output_dir / "pred.csv"

    problems = load_problems(input_path)
    if args.limit is not None:
        problems = problems[: args.limit]

    client = None
    if not args.dry_run:
        client = NvidiaChatClient(NvidiaConfig.from_env())

    predictions = [
        solve_problem(problem, client, dry_run=args.dry_run, verify=args.verify)
        for problem in problems
    ]
    write_predictions(output_path, predictions)
    if args.trace_dir:
        write_trace(Path(args.trace_dir), predictions)

    print(f"Loaded {len(problems)} problems from {input_path}")
    print(f"Wrote predictions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
