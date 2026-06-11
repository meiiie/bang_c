"""Score the per-bucket battery: accuracy per arm + the PAIRED diff that decides.

Promotion rule (anti-overfit discipline): promote `router` over `self-consistency`
only if it wins per-bucket with no overall regression. The paired comparison
(items where exactly one arm is correct) is the decision signal — at n=150 the
unpaired accuracies are ±~3pp noise, the paired diff is much tighter.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

# bucket -> (incumbent, candidate); see run_battery.sh for the arm rationale.
BUCKET_ARMS = {
    "quant": ("self-consistency", "router"),
    "reading": ("self-consistency", "reading"),
    "civics": ("self-consistency", "rag"),
}


def read_csv_answers(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["qid"]: row["answer"].strip().upper() for row in csv.DictReader(handle)}


def strategy_distribution(trace_dir: Path) -> Counter:
    counts: Counter = Counter()
    trace_file = trace_dir / "predictions.trace.jsonl"
    if not trace_file.exists():
        return counts
    with trace_file.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                counts[json.loads(line).get("strategy", "?")] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devsets", default="/workspace/devsets")
    parser.add_argument("--out", default="/workspace/out")
    args = parser.parse_args()
    devsets = Path(args.devsets)
    out = Path(args.out)

    overall = {"incumbent": [0, 0], "candidate": [0, 0]}  # correct, total
    for bucket, arms in BUCKET_ARMS.items():
        gold = read_csv_answers(devsets / f"{bucket}.gold.csv")
        print(f"\n## {bucket} (n={len(gold)})  arms={arms}")
        answers: dict[str, dict[str, str]] = {}
        for role, arm in zip(("incumbent", "candidate"), arms):
            pred_path = out / f"{bucket}-{arm}" / "pred.csv"
            if not pred_path.exists():
                print(f"  {arm}: MISSING {pred_path}")
                continue
            preds = read_csv_answers(pred_path)
            answers[arm] = preds
            correct = sum(1 for qid, answer in gold.items() if preds.get(qid) == answer)
            overall[role][0] += correct
            overall[role][1] += len(gold)
            print(f"  {arm:18s} {correct}/{len(gold)} = {100 * correct / len(gold):.2f}%")
            distribution = strategy_distribution(out / f"{bucket}-{arm}" / "traces")
            if distribution:
                print(f"    strategies: {dict(distribution)}")
        if len(answers) == 2:
            a, b = arms
            a_only = [q for q in gold if answers[a].get(q) == gold[q] != answers[b].get(q)]
            b_only = [q for q in gold if answers[b].get(q) == gold[q] != answers[a].get(q)]
            print(f"  paired: {a} only correct={len(a_only)}, {b} only correct={len(b_only)}")
            print(f"    {b}-wins: {b_only[:10]}")
            print(f"    {b}-losses: {a_only[:10]}")

    print("\n## overall (incumbent vs candidate, all buckets pooled)")
    for role, (correct, total) in overall.items():
        if total:
            print(f"  {role:18s} {correct}/{total} = {100 * correct / total:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
