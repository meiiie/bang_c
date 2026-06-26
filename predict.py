#!/usr/bin/env python3
"""HackAIthon 2026 - Bang C, Round 2 submission entry point.

Reads the BTC-mounted test file (default ``/code/private_test.json``), runs the
validated Qwen3-4B self-consistency (k=1 / chain-of-thought) engine ONE item at a
time while timing each item, then writes the two BTC artifacts:

    submission.csv        ->  qid,answer
    submission_time.csv   ->  qid,answer,time      (per-sample inference seconds)

It reuses the exact contest solving path (``solve_problem`` +
``repair_predictions_for_contract``), so accuracy matches the harness; only the
BTC I/O contract and per-sample timing are added in this wrapper. The engine,
model, prompts and config are untouched.

Usage:
    python predict.py [INPUT_FILE]

Env:
    NEKO_DRY_RUN=1   Solve with the deterministic heuristic (no model / no GPU).
                     For wiring + output-format tests only.
    NEKO_INPUT=...   Explicit input path (overrides the default search).
"""
from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

# Make the packaged engine importable whether run from /code, /app, or a checkout.
_HERE = Path(__file__).resolve().parent
for _cand in (_HERE / "src", Path("/code/src"), Path("/app/src")):
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

from hackaithon_c.config import load_config
from hackaithon_c.evaluation import repair_predictions_for_contract
from hackaithon_c.loader import load_problems
from hackaithon_c.solver import solve_problem
from hackaithon_c.workflows import resolve_workflow

# BTC mounts the private test at /code/private_test.json; the rest are dev/safety fallbacks.
_INPUT_CANDIDATES = (
    "/code/private_test.json",
    "/code/private_test.csv",
    "/data/private_test.json",
    "/data/private_test.csv",
    "/data/public_test.json",
    "/data/public_test.csv",
)
# Write artifacts where BTC expects them (working dir / /code) AND /output as insurance.
_OUTPUT_DIRS = ("/code", "/output", ".")
_WORKFLOW = "self-consistency"  # k=1 CoT -- the validated contest path


def _dry_run_enabled() -> bool:
    if os.environ.get("NEKO_DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return "--dry-run" in sys.argv[1:]


def _resolve_input() -> Path:
    for arg in sys.argv[1:]:
        if not arg.startswith("-") and Path(arg).is_file():
            return Path(arg)
    env = os.environ.get("NEKO_INPUT") or os.environ.get("HACKC_INPUT")
    if env and Path(env).is_file():
        return Path(env)
    for cand in _INPUT_CANDIDATES:
        if Path(cand).is_file():
            return Path(cand)
    # Last resort: any *test*.{json,csv} under the usual roots.
    for base in ("/code", "/data", "."):
        directory = Path(base)
        if directory.is_dir():
            for pattern in ("*test*.json", "*test*.csv"):
                hits = sorted(directory.glob(pattern))
                if hits:
                    return hits[0]
    raise FileNotFoundError(
        "No test input found (looked for /code/private_test.json and fallbacks)."
    )


def _writable_output_dirs() -> list[Path]:
    override = os.environ.get("NEKO_OUTPUT_DIR", "").strip()
    candidates = (override,) if override else _OUTPUT_DIRS
    targets: list[Path] = []
    for raw in candidates:
        try:
            path = Path(raw).resolve()
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".neko_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception:
            continue
        if path not in targets:
            targets.append(path)
    return targets or [Path(".").resolve()]


def _write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> int:
    dry_run = _dry_run_enabled()
    input_path = _resolve_input()
    config = load_config(None)
    workflow = resolve_workflow(config, _WORKFLOW)
    strategy = workflow.strategy if workflow else config.default_strategy

    problems = load_problems(input_path)
    print(
        f"[predict] loaded {len(problems)} problems from {input_path} "
        f"(strategy={strategy}, dry_run={dry_run})",
        flush=True,
    )

    client = None
    if not dry_run:
        from hackaithon_c.model_client import build_chat_client

        client = build_chat_client(config, provider=None)
        try:
            from hackaithon_c.run import validate_runtime_model

            validate_runtime_model(client.model, config)
        except Exception as exc:  # eligibility guard must never block producing output
            print(f"[predict] WARNING: model validation: {exc}", file=sys.stderr, flush=True)

    predictions: list = []
    times: dict[str, float] = {}
    total = len(problems)
    wall_start = time.perf_counter()
    for index, problem in enumerate(problems, 1):
        start = time.perf_counter()
        try:
            prediction = solve_problem(
                problem,
                client,
                dry_run=dry_run,
                verify=False,
                strategy=strategy,
                fail_fast=False,
                config=config,
                challenger=None,
            )
            predictions.append(prediction)
        except Exception as exc:  # one bad item must never zero the whole run
            print(
                f"[predict] qid={problem.qid} ERROR {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
        times[problem.qid] = time.perf_counter() - start
        if index % 50 == 0 or index == total:
            print(f"[predict] {index}/{total} done", flush=True)

    # Guarantee every qid carries a letter valid for its own problem, in input order.
    predictions = repair_predictions_for_contract(problems, predictions)

    submission_rows = [(p.qid, p.answer) for p in predictions]
    time_rows = [(p.qid, p.answer, f"{times.get(p.qid, 0.0):.4f}") for p in predictions]

    targets = _writable_output_dirs()
    for directory in targets:
        _write_csv(directory / "submission.csv", ["qid", "answer"], submission_rows)
        _write_csv(
            directory / "submission_time.csv", ["qid", "answer", "time"], time_rows
        )

    elapsed = time.perf_counter() - wall_start
    print(
        "[predict] wrote submission.csv + submission_time.csv to: "
        + ", ".join(str(d) for d in targets),
        flush=True,
    )
    print(
        f"[predict] {total} items in {elapsed:.1f}s "
        f"(avg {elapsed / max(1, total):.3f}s/item)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
