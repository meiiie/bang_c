from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.accuracy_summary is None and args.mtp_summary is None:
        raise ValueError("provide --accuracy-summary, --mtp-summary, or both")

    report: dict[str, Any] = {
        "verdict": "pass",
        "accuracy": None,
        "mtp": None,
    }
    problems = []

    if args.accuracy_summary is not None:
        accuracy = _assess_accuracy(
            args.accuracy_summary,
            min_delta=args.min_accuracy_delta,
            max_losses=args.max_accuracy_losses,
        )
        report["accuracy"] = accuracy
        problems.extend(accuracy["problems"])

    if args.mtp_summary is not None:
        mtp = _assess_mtp(
            args.mtp_summary,
            min_speedup=args.min_mtp_speedup,
            require_content_match=not args.allow_mtp_content_mismatch,
        )
        report["mtp"] = mtp
        problems.extend(mtp["problems"])

    if problems:
        report["verdict"] = "fail"
        report["problems"] = problems
    else:
        report["problems"] = []
        report["decision"] = (
            "ready_for_owner_review_not_submission"
            if report["accuracy"] is not None
            else "speed_candidate_ready_for_owner_review"
        )

    _emit(report, args.summary_json)
    return 0 if report["verdict"] == "pass" else 2


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assess measured experiment artifacts and decide whether they are "
            "ready for owner review. This never calls a model or submits files."
        )
    )
    parser.add_argument(
        "--accuracy-summary",
        type=Path,
        default=None,
        help="measured-gate.json from scripts/compare_candidate_predictions.py",
    )
    parser.add_argument(
        "--mtp-summary",
        type=Path,
        default=None,
        help="summary.txt from scripts/gpu/run_mtp_server.sh",
    )
    parser.add_argument("--summary-json", type=Path, default=None, help="Optional JSON report path")
    parser.add_argument("--min-accuracy-delta", type=int, default=1)
    parser.add_argument("--max-accuracy-losses", type=int, default=0)
    parser.add_argument("--min-mtp-speedup", type=float, default=1.4)
    parser.add_argument(
        "--allow-mtp-content-mismatch",
        action="store_true",
        help="Do not fail MTP when a measured MTP row differs from baseline content.",
    )
    return parser.parse_args(argv)


def _assess_accuracy(
    path: Path,
    *,
    min_delta: int,
    max_losses: int,
) -> dict[str, Any]:
    payload = _read_json_file(path)
    required = ("delta", "losses", "candidate_changes", "candidate", "baseline")
    missing = [key for key in required if key not in payload]
    problems = []
    if missing:
        problems.append(f"accuracy summary missing fields: {', '.join(missing)}")
        return {"path": str(path), "ok": False, "problems": problems}

    delta = int(payload["delta"])
    losses = int(payload["losses"])
    ok = True
    if delta < min_delta:
        ok = False
        problems.append(
            f"accuracy delta {delta} is below required minimum {min_delta}"
        )
    if losses > max_losses:
        ok = False
        problems.append(
            f"accuracy losses {losses} exceed allowed maximum {max_losses}"
        )
    return {
        "path": str(path),
        "ok": ok,
        "delta": delta,
        "losses": losses,
        "candidate_changes": int(payload["candidate_changes"]),
        "candidate": payload["candidate"],
        "baseline": payload["baseline"],
        "reference": payload.get("reference"),
        "min_delta": min_delta,
        "max_losses": max_losses,
        "problems": problems,
    }


def _assess_mtp(
    path: Path,
    *,
    min_speedup: float,
    require_content_match: bool,
) -> dict[str, Any]:
    rows = _read_summary_json_lines(path)
    problems = []
    verdict_rows = [row for row in rows if "verdict" in row]
    if not verdict_rows:
        problems.append("MTP summary missing final verdict row")
    elif verdict_rows[-1].get("verdict") != "pass":
        problems.append(f"MTP summary verdict is {verdict_rows[-1].get('verdict')!r}")

    mtp_rows = [
        row
        for row in rows
        if str(row.get("label", "")).startswith("mtp_")
    ]
    if not mtp_rows:
        problems.append("MTP summary has no mtp_* measurement rows")
        return {
            "path": str(path),
            "ok": False,
            "best_label": None,
            "best_speedup": None,
            "min_speedup": min_speedup,
            "rows": [],
            "problems": problems,
        }

    usable_rows = []
    for row in mtp_rows:
        speedup = row.get("speedup_vs_baseline_median")
        content_matches = row.get("content_matches_baseline")
        if require_content_match and content_matches is not True:
            problems.append(
                f"{row.get('label')} content_matches_baseline is {content_matches!r}"
            )
            continue
        if not isinstance(speedup, int | float):
            problems.append(f"{row.get('label')} missing numeric speedup")
            continue
        usable_rows.append(row)

    best = max(
        usable_rows,
        key=lambda row: float(row["speedup_vs_baseline_median"]),
        default=None,
    )
    best_speedup = (
        float(best["speedup_vs_baseline_median"])
        if best is not None
        else None
    )
    if best_speedup is None or best_speedup < min_speedup:
        problems.append(
            f"MTP best speedup {best_speedup} is below required minimum {min_speedup}"
        )
    return {
        "path": str(path),
        "ok": not problems,
        "best_label": best.get("label") if best else None,
        "best_speedup": best_speedup,
        "min_speedup": min_speedup,
        "require_content_match": require_content_match,
        "rows": [
            {
                "label": row.get("label"),
                "speedup_vs_baseline_median": row.get("speedup_vs_baseline_median"),
                "content_matches_baseline": row.get("content_matches_baseline"),
                "draft_acceptance_present": row.get("draft_acceptance_present"),
                "draft_acceptance_rate_median": row.get("draft_acceptance_rate_median"),
            }
            for row in mtp_rows
        ],
        "problems": problems,
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_summary_json_lines(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{path}:{line_number} is not valid JSON: {error.msg}"
                ) from error
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append(payload)
    return rows


def _emit(report: dict[str, Any], path: Path | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)
