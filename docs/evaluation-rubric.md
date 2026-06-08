# Harness Evaluation Rubric

Status: Active
Last updated: 2026-06-08

This rubric is for evaluating the harness itself. It is not the contest
accuracy score.

## Categories

| Category | Weight | Meaning |
| --- | ---: | --- |
| Contract | 40 | Output has correct path, columns, row count, qids, and answer letters. |
| Reproducibility | 20 | Run can be reproduced from source, config, Docker, and environment variables. |
| Robustness | 20 | The run avoids avoidable fallbacks and handles schema/language variation. |
| Runtime discipline | 10 | Final runtime stays within `/data` -> `/output/pred.csv`. |
| Traceability | 10 | Dev runs produce trace and summary artifacts for review. |

## Current Scoring

`evaluation.py` computes a simple harness score:

- contract score is full when prediction validation passes;
- reproducibility and runtime discipline are granted for using the configured
  harness path;
- robustness is reduced by fallback ratio;
- traceability is granted when `--trace-dir` is enabled.

This score is intentionally conservative. It tells the team whether the harness
is healthy enough to run accuracy experiments.

## Accuracy Evaluation

Accuracy needs a separate labeled dataset or trusted public leaderboard
feedback. Do not infer accuracy from smoke tests. Smoke tests only prove the
runtime path works.

Recommended accuracy loop:

1. Run public test with trace enabled.
2. Submit `pred.csv` if leaderboard flow is available.
3. Record score and prompt/config version.
4. Analyze low-confidence and changed-answer traces.
5. Change one technique at a time.
6. Re-run the same sample and compare stability.

## Workflow Comparison

Use `scripts/evaluate.ps1` for development-only workflow comparison. The script
runs selected workflows as `--run-dir` sessions, stores artifacts under
`eval-runs/`, and writes `eval-summary.json` plus `eval-report.md` for the
whole eval run. It reports:

- contract validity;
- harness score;
- average confidence;
- fallback count;
- answer changes compared with the first run;
- reviewer verdict and trace-comparison verdict for each run;
- a selected candidate ranked by valid contract, stability, review verdict,
  fallback count, harness score, and confidence.

Inspect `predictions.trace.jsonl` for each changed or low-confidence answer.
The `trace` field records the agent-style path that produced the answer, which
helps separate classifier mistakes, solver drift, repair events, verifier
changes, and tournament synthesis issues.

Run `neko-core --review-trace <trace-dir>` after experiments to get a compact
reviewer verdict. A `WARN` verdict is expected for heuristic or low-confidence
development runs; a `FAIL` verdict means trace artifacts are missing, counts do
not match, the prediction contract is invalid, or a trace step is blocked.
Run `neko-core --review-tasks <trace-dir> --run-dir <path>` to convert those
findings into a queue of concrete follow-up tasks.
Use `run-manifest.json` in the same trace directory to compare config/input
hashes before trusting differences between two runs.
Use `neko-core --compare-traces <left> <right>` to separate real answer changes
from config/input/model drift.

The default run repeats `quick-dry-run` twice to check reproducibility without
requiring an API key. When model access is available, compare workflows such as
`contest-auto`, `verify-all`, or `tournament` explicitly.
