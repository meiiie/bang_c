#!/usr/bin/env python
"""Export a representative harness prompt for llama.cpp MTP benchmarking.

This is development tooling only. It does not call a model, does not write
pred.csv, and does not include labels/answers. The output is intended for
`scripts/gpu/run_mtp_server.sh` so MTP speed is measured on a harness-shaped
prompt instead of a toy arithmetic prompt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hackaithon_c.classifier import classify_problem
from hackaithon_c.config import load_config
from hackaithon_c.loader import load_problems
from hackaithon_c.prompting import (
    PromptBundle,
    build_prompt,
    build_reading_prompt,
    build_reasoning_prompt,
    load_exemplars,
    with_safety_clause,
)
from hackaithon_c.schema import Problem


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a representative MTP benchmark prompt")
    parser.add_argument("--input", required=True, help="Contest-style JSON/CSV input file")
    parser.add_argument("--config", default=None, help="Optional harness config JSON")
    parser.add_argument(
        "--selection",
        choices=("first", "longest", "median-length"),
        default="longest",
        help="Which input item to export. Default longest stresses realistic context length.",
    )
    parser.add_argument(
        "--prompt-mode",
        choices=("reasoning", "direct", "reading"),
        default="reasoning",
        help="Prompt family to export. Default reasoning matches self-consistency.",
    )
    parser.add_argument("--prompt-out", default=None, help="Optional file for prompt text")
    parser.add_argument("--messages-out", default=None, help="Optional OpenAI chat messages JSON file")
    parser.add_argument("--metadata-out", default=None, help="Optional file for prompt metadata JSON")
    return parser.parse_args(argv)


def choose_problem(problems: list[Problem], selection: str) -> tuple[int, Problem]:
    if not problems:
        raise ValueError("input contains no problems")
    if selection == "first":
        return 0, problems[0]
    scored = sorted(enumerate(problems), key=lambda item: _problem_length(item[1]))
    if selection == "longest":
        return scored[-1]
    return scored[len(scored) // 2]


def build_bundle(problem: Problem, mode: str, config_path: str | None) -> PromptBundle:
    config = load_config(Path(config_path)) if config_path else load_config()
    profile = classify_problem(problem, config)
    if mode == "direct":
        return build_prompt(problem, profile, config=config)
    exemplars = load_exemplars(config.reasoning_few_shot_path)
    if mode == "reading":
        bundle = build_reading_prompt(
            problem,
            max_tokens=config.reasoning_max_tokens,
            exemplars=exemplars,
        )
    else:
        bundle = build_reasoning_prompt(
            problem,
            max_tokens=config.reasoning_max_tokens,
            exemplars=exemplars,
        )
    return with_safety_clause(bundle, config.enable_safety_refusal)


def render_completion_prompt(bundle: PromptBundle) -> str:
    return (
        "SYSTEM:\n"
        f"{bundle.system_prompt}\n\n"
        "USER:\n"
        f"{bundle.user_prompt}\n\n"
        "ASSISTANT:\n"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    problems = load_problems(Path(args.input))
    index, problem = choose_problem(problems, args.selection)
    bundle = build_bundle(problem, args.prompt_mode, args.config)
    prompt = render_completion_prompt(bundle)
    metadata = {
        "schema_version": "neko_core.mtp_benchmark_prompt.v1",
        "input_count": len(problems),
        "selected_index": index,
        "selection": args.selection,
        "prompt_mode": args.prompt_mode,
        "prompt_variant": bundle.variant,
        "max_tokens": bundle.max_tokens,
        "choice_count": len(problem.choices),
        "question_chars": len(problem.question),
        "prompt_chars": len(prompt),
        "qid_sha256": hashlib.sha256(problem.qid.encode("utf-8")).hexdigest(),
    }
    if args.prompt_out:
        Path(args.prompt_out).write_text(prompt, encoding="utf-8")
    else:
        print(prompt, end="")
    if args.messages_out:
        messages_payload = {
            "schema_version": "neko_core.mtp_benchmark_messages.v1",
            "messages": [
                {"role": "system", "content": bundle.system_prompt},
                {"role": "user", "content": bundle.user_prompt},
            ],
            "max_tokens": bundle.max_tokens,
            "prompt_variant": bundle.variant,
        }
        Path(args.messages_out).write_text(
            json.dumps(messages_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.metadata_out:
        Path(args.metadata_out).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


def _problem_length(problem: Problem) -> int:
    return len(problem.question) + sum(len(choice) for choice in problem.choices)


if __name__ == "__main__":
    raise SystemExit(main())
