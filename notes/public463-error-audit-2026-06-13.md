# Public 463 error audit against 91.79 reference - 2026-06-13

Status: dev-only measurement note. Do not copy qids, public-answer facts, or
leaderboard-derived observations into `src/`, `configs/`, tests, Docker runtime,
or submission logic.

## Purpose

The owner asked to inspect the current 463-question public-set answers before
doing more accuracy work: where are the remaining mistakes, what areas do they
belong to, and why can another artifact reach the 89-92 band while the shipped
Gemma path sits around 88.55?

This audit uses:

- Input: `C:\Users\Admin\Downloads\public-test_1780368312.json`
- Best current Gemma/self-consistency artifact checked here:
  `data/q4results/router_pred_sc.csv`
- 91.79 pseudo-reference / frontier hand-solve artifact:
  `data/q4results/claude_public463_pred_v2_webfixed.csv`

Important caveat: agreement with the 91.79 pseudo-reference is an internal
analysis signal, not the contest grader. It is useful for error structure, not
for hardcoding or automatic promotion.

## Artifact agreement

Measured directly from the CSV files on 2026-06-13:

| artifact | agreement vs 91.79 reference | different rows |
|---|---:|---:|
| `data/q4results/router_pred_sc.csv` | 429/463 = 92.66% | 34 |
| `run-full-public-contest-strict-v5/output/pred.csv` | 424/463 = 91.58% | 39 |
| `run-full-public-contest-strict-v4/output/pred.csv` | 422/463 = 91.14% | 41 |
| `data/q4results/31bq4_public463_pred.csv` | 427/463 = 92.22% | 36 |
| `data/q4results/claude_public463_pred.csv` | 459/463 = 99.14% | 4 |

Interpretation:

- `router_pred_sc.csv` is the best current Gemma artifact among the measured
  local files, so use it as the current error-audit baseline.
- Older contest-strict runs differ more from the 91.79 reference; do not use
  them as the primary baseline for diagnosis.
- Dense 31B is not a clean accuracy win: it is close, but worse than the best
  26B self-consistency artifact here, and much slower.
- The Claude/frontier artifact mostly fixes the same residual band, which
  strongly suggests the remaining gap is knowledge/selection quality, not CSV
  contract or parsing.

## Structural buckets for the 34 current disagreements

Using the harness classifier on the current 34 disagreements:

| bucket | count |
|---|---:|
| short | 24 |
| calculation | 3 |
| many_choice | 3 |
| negative | 2 |
| reading | 1 |
| general | 1 |

Choice-count split:

| choices | count |
|---|---:|
| 4 choices | 30 |
| 10 choices | 4 |

Feature split:

| classifier features | count |
|---|---:|
| none | 20 |
| `has_legal_admin,has_legal_admin_strong` | 3 |
| `has_many_choices` | 3 |
| `has_negative` | 2 |
| `has_legal_admin` | 2 |
| `has_calculation` | 2 |
| `has_long_context,has_legal_admin,has_legal_admin_strong` | 1 |
| `has_many_choices,has_calculation` | 1 |

Key reading:

- The remaining failures are not mainly long-passage reading comprehension.
- They are not mainly 10-choice position-bias failures either.
- The largest class is short factual/SGK/local/current-policy questions, many
  of which the structural router sees as plain `short` with no special feature.
- A structural router alone is unlikely to recover these, because most of the
  hard questions do not advertise themselves with obvious surface markers.

## Domain map of the 34 disagreements

Manual domain grouping from the question text:

| domain group | count | qids |
|---|---:|---|
| VN legal/admin/current-policy facts | 7 | `test_0022`, `test_0058`, `test_0070`, `test_0087`, `test_0224`, `test_0301`, `test_0354` |
| VN school civics/history/HCM/literature/geography | 10 | `test_0048`, `test_0061`, `test_0115`, `test_0200`, `test_0209`, `test_0274`, `test_0313`, `test_0336`, `test_0370`, `test_0396` |
| Religion/local Buddhist/philosophy facts | 5 | `test_0001`, `test_0030`, `test_0068`, `test_0074`, `test_0401` |
| Quantitative/technical/science/IT | 6 | `test_0063`, `test_0110`, `test_0143`, `test_0173`, `test_0271`, `test_0389` |
| Business/econ/ESG/environment/ethics | 6 | `test_0109`, `test_0151`, `test_0228`, `test_0258`, `test_0441`, `test_0454` |

This is the main answer to "vấn đề ở đâu":

1. A large share is knowledge-bound, especially Vietnamese current/admin facts,
   SGK-style civics/history/geography, and local religious trivia.
2. A smaller but meaningful share is careful reasoning over familiar knowledge:
   causal qualifier, "not due to", all-options enumeration, ethics/trust, or
   choosing the most exact answer.
3. Pure calculation exists, but it is not the dominant remaining bucket.
4. Broad RAG is still unlikely to help reading questions, but a narrow offline
   corpus for the VN-current/admin/SGK slice may have real headroom if measured
   carefully.

## Candidate artifacts are not safe selectors by themselves

Compared against `router_pred_sc.csv`:

| candidate artifact | changes | fixes current mistakes | false flips | neutral |
|---|---:|---:|---:|---:|
| `run-full-public-contest-strict-v5/output/pred.csv` | 53 | 23 | 28 | 2 |
| `data/q4results/31bq4_public463_pred.csv` | 42 | 19 | 21 | 2 |
| `data/q4results/claude_public463_pred.csv` | 33 | 31 | 1 | 1 |

Meaning:

- There is real oracle headroom: alternate answers often contain the reference
  answer.
- But naive "switch to another Gemma/31B artifact" is not safe because fixes and
  false flips are almost balanced.
- The next possible accuracy lever is not another blanket workflow; it is a
  selector/ranker that knows when to keep the current answer and when to trust a
  candidate.

## Practical diagnosis

What not to do:

- Do not add per-qid fixes.
- Do not revive public-derived deterministic rules.
- Do not route broadly to TIR; measured router/TIR was much worse because it
  false-flipped many correct answers.
- Do not use 31B as the final default; it is not a measured win here and has a
  major time cost.

What might still work, if measured:

1. Oracle/headroom analyzer.
   - For each question, collect current answer plus candidate answers from
     controlled variants.
   - Measure whether the right answer appears in the pool and which signals
     predict it.

2. Lightweight selector/ranker.
   - Features: current answer confidence, candidate agreement, answer stability,
     option-order stability, concise rationale consistency, legal/admin marker,
     exact-number marker, and "all options must be enumerated" marker.
   - Train/tune only on non-public or synthetic/proxy data. Public 463 can be
     used as an audit signal, not training labels.

3. Narrow offline knowledge augmentation.
   - Target only VN legal/admin/current-policy and SGK civic/history/geography
     buckets.
   - Retrieval must be fallible evidence, not a hard truth source.
   - Any corpus must be packaged offline and tested on a non-public proxy before
     promotion.

4. Precision prompts for "most exact answer" tasks.
   - Some failures are not missing facts but premature first-true-option picks.
   - A cheap verifier for low-confidence short questions may help if it is
     pairwise and selective, not always-on.

## Immediate next step

Build a read-only oracle/headroom report script or notebook-equivalent that
takes:

```text
--input public-test_1780368312.json
--reference data/q4results/claude_public463_pred_v2_webfixed.csv
--baseline data/q4results/router_pred_sc.csv
--candidate NAME=path/to/pred.csv ...
```

and emits:

- agreement summary;
- wrong-current buckets;
- candidate fixes/losses;
- per-domain headroom;
- changed-answer audit.

Do this before any solver edit. The current evidence says the next battle is
candidate selection and narrow knowledge, not another broad router.
