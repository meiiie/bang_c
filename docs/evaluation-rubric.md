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

