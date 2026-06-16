#!/usr/bin/env python3
"""Read-only error / headroom analyzer over pred.csv artifacts.

DEV / eval ONLY. It is never imported by the runtime and writes nothing to src/, configs/, tests/,
or the submission path. It buckets every question with the SAME harness classifier the router/gate
see (``classify_problem``), so per-cluster numbers reflect the real solving structure, and reports:

  * test composition by cluster (kind + features + choice-count),
  * per-cluster accuracy for the baseline and each candidate (when a reference/gold is given),
  * the changed-answer audit baseline-vs-candidate (fixes / false-flips / neutral),
  * per-cluster headroom (how many baseline-wrong items a candidate could recover).

This is the standing "optimize what you measure" loop: a lever is judged on its TARGET cluster with a
no-regression view, so a wash (e.g. the law-corpus -2) is caught before it ships, not after.

Usage:
  python scripts/analyze_errors.py --input test.json \
      --baseline base=runs/baseline/pred.csv \
      [--candidate altA=runs/a/pred.csv --candidate altB=runs/b/pred.csv ...] \
      [--reference data/devsets/quant.gold.csv]

A reference is a ``qid,answer`` CSV: a labeled dev gold (-> TRUE accuracy) OR a frontier/oracle pred
(-> agreement signal only; NEVER hardcode answers from it — it is not the contest grader).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Import the harness so clusters match the live classifier exactly.
_REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

from hackaithon_c.classifier import classify_problem  # noqa: E402
from hackaithon_c.config import load_config  # noqa: E402
from hackaithon_c.loader import load_problems  # noqa: E402


def _parse_named(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"expected NAME=path, got '{value}'")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError(f"expected NAME=path, got '{value}'")
    return name, path


def _load_pred(path: str) -> dict[str, str]:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows or "qid" not in rows[0] or "answer" not in rows[0]:
        raise ValueError(f"{path}: expected a qid,answer CSV header")
    return {r["qid"]: (r["answer"] or "").strip() for r in rows}


def _cluster(profile) -> str:
    """A readable cluster label: the structural kind, refined by the strongest feature so the
    legal/admin and long-context slices (where RAG/reading decisions happen) are visible."""
    kind = str(profile.kind)
    feats = set(profile.features)
    if "has_legal_admin_strong" in feats:
        return f"{kind}+legal_admin_strong"
    if "has_legal_admin" in feats:
        return f"{kind}+legal_admin"
    if "has_long_context" in feats and kind != "reading":
        return f"{kind}+long_context"
    return kind


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:5.1f}%" if d else "  n/a"


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only per-cluster error/headroom analysis.")
    ap.add_argument("--input", required=True, help="test JSON/CSV (qid,question,choices)")
    ap.add_argument("--baseline", required=True, type=_parse_named, help="NAME=pred.csv (the shippable answer)")
    ap.add_argument("--candidate", action="append", default=[], type=_parse_named, help="NAME=pred.csv (repeatable)")
    ap.add_argument("--reference", default=None, help="qid,answer CSV: labeled gold (accuracy) or oracle (agreement)")
    args = ap.parse_args()

    config = load_config()
    problems = load_problems(Path(args.input))
    cluster_of = {p.qid: _cluster(classify_problem(p, config)) for p in problems}
    nchoices = {p.qid: len(p.choices) for p in problems}
    order = [p.qid for p in problems]
    clusters = sorted(set(cluster_of.values()))

    base_name, base = args.baseline[0], _load_pred(args.baseline[1])
    candidates = [(name, _load_pred(path)) for name, path in args.candidate]
    ref = _load_pred(args.reference) if args.reference else None

    print(f"\n=== INPUT: {len(problems)} questions | baseline='{base_name}' | "
          f"candidates={[n for n, _ in candidates]} | reference={'yes' if ref else 'none'} ===")

    # 1. Composition by cluster
    print("\n--- composition by cluster ---")
    comp = {c: sum(1 for q in order if cluster_of[q] == c) for c in clusters}
    for c in sorted(comp, key=lambda x: -comp[x]):
        print(f"  {c:<28} {comp[c]:>4}")
    cc = {}
    for q in order:
        cc[nchoices[q]] = cc.get(nchoices[q], 0) + 1
    print("  choice-count:", {k: cc[k] for k in sorted(cc)})

    # 2. Per-cluster accuracy (needs a reference)
    if ref:
        preds = [(base_name, base)] + candidates
        print("\n--- per-cluster accuracy vs reference (correct/scored) ---")
        header = "  " + "cluster".ljust(28) + "".join(f"{n[:12]:>14}" for n, _ in preds)
        print(header)
        for c in clusters:
            qs = [q for q in order if cluster_of[q] == c and q in ref]
            cells = ""
            for _, pred in preds:
                scored = [q for q in qs if q in pred]
                correct = sum(1 for q in scored if pred[q] == ref[q])
                cells += f"{_pct(correct, len(scored))}({len(scored):>3})".rjust(14)
            print(f"  {c:<28}{cells}")
        # overall
        cells = ""
        for _, pred in preds:
            scored = [q for q in order if q in ref and q in pred]
            correct = sum(1 for q in scored if pred[q] == ref[q])
            cells += f"{_pct(correct, len(scored))}({len(scored):>3})".rjust(14)
        print(f"  {'OVERALL':<28}{cells}")

    # 3. Changed-answer audit: baseline vs each candidate
    for name, pred in candidates:
        common = [q for q in order if q in base and q in pred]
        changed = [q for q in common if base[q] != pred[q]]
        print(f"\n--- changed-answer audit: '{name}' vs baseline '{base_name}' "
              f"({len(changed)} changed of {len(common)}) ---")
        by_cluster = {}
        for q in changed:
            by_cluster.setdefault(cluster_of[q], []).append(q)
        for c in sorted(by_cluster, key=lambda x: -len(by_cluster[x])):
            qs = by_cluster[c]
            tag = ""
            if ref:
                fix = sum(1 for q in qs if q in ref and base[q] != ref[q] and pred[q] == ref[q])
                flip = sum(1 for q in qs if q in ref and base[q] == ref[q] and pred[q] != ref[q])
                neutral = len(qs) - fix - flip
                tag = f"  [fix={fix} false-flip={flip} neutral={neutral}]"
            print(f"  {c:<28} {len(qs):>3}{tag}  {qs[:8]}")
        if ref:
            scored = [q for q in changed if q in ref]
            fix = sum(1 for q in scored if base[q] != ref[q] and pred[q] == ref[q])
            flip = sum(1 for q in scored if base[q] == ref[q] and pred[q] != ref[q])
            net = fix - flip
            verdict = "SAFE (net+)" if net > 0 else ("WASH" if net == 0 else "UNSAFE (net-)")
            print(f"  => TOTAL fix={fix} false-flip={flip} net={net:+d}  {verdict}")

    # 4. Headroom (needs a reference): where the baseline is wrong, and what's recoverable
    if ref:
        print("\n--- per-cluster headroom (baseline-wrong | recoverable by any candidate) ---")
        for c in clusters:
            qs = [q for q in order if cluster_of[q] == c and q in ref and q in base]
            wrong = [q for q in qs if base[q] != ref[q]]
            recoverable = [q for q in wrong if any(pred.get(q) == ref[q] for _, pred in candidates)]
            if wrong:
                print(f"  {c:<28} wrong={len(wrong):>3} / {len(qs):<3}  recoverable={len(recoverable)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
