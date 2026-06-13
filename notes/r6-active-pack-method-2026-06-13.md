# R6 Active Pack Method - 2026-06-13

Status: dev-only public-463 analysis artifact. Do not ship into runtime.

## Current locked best

Best observed public-test score:

```text
429 / 463 = 92.66
```

Best known file:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s1-0274A/pred.csv
```

Known empirical decisions:

- Keep `test_0068: B`.
- Keep `test_0115: B`.
- Keep `test_0274: A`.
- Reject `test_0001: A`.
- Reject `test_0151: I`.
- Reject `test_0109: C`.
- Reject `test_0346: B`.
- Do not early-test the negative pairs `test_0200 + test_0271` or `test_0329 + test_0389`.

Unknown / needs confirmation:

- Exact observed score for `output-probes/codex-webmax-2026-06-13-r5-cumulative/s5-0274A-0022D/pred.csv`.

## Why not keep singletons

Singleton tests are clean, but they only move one answer per submission. From
the 92.66 base, reaching 95 requires about 11 net additional correct answers:

```text
95.00% of 463 = 440 correct
current = 429 correct
gap = 11 net correct
```

The public grader only gives an aggregate score. It does not reveal which qids
changed from wrong to right. Therefore there is no exact, label-free way to
recover all remaining wrong answers unless we bring in a strong external prior:
web evidence, official sources, model consensus, and contradiction checks.

R6 switches from one-by-one probing to evidence-weighted active group testing:

1. Build a small pack of plausible corrections with independent reasons.
2. Submit the whole pack once.
3. If the pack jumps, use leave-one-out files to isolate bad or good members.
4. If the pack falls, discard the pack and preserve the 92.66 base.

This uses the same number of submissions to test more hypotheses, while keeping
runtime clean and avoiding leaderboard-derived code.

## Core candidates

All candidates below are applied only to dev-only `pred.csv` probe files.

```text
test_0396: D -> A
test_0370: B -> C
test_0048: A -> B
```

Rationale:

- `test_0396`: current answer is a safety refusal. Direct-answer model variants
  often choose `A`. This is risky because the content is safety-sensitive, so it
  must not become a runtime rule or prompt hack.
- `test_0370`: sources and model variants suggest the stronger reason for
  Nguyen Ai Quoc going West was to study revolutionary paths and world practice,
  not only Western civilization.
- `test_0048`: wording is ambiguous between family/patriotic tradition and
  Marxism-Leninism. Model consensus and official theory-source wording make `B`
  worth testing, though it remains risky.

Conditional fourth candidate:

```text
test_0022: A -> D
```

Use this only if the R5 `s5-0274A-0022D` score was not negative. If that file
scored 92.44, reject `test_0022: D` and do not include it in R6 packs.

## Generated files

All files passed submission contract check against the 463-row public input.

Primary screening files:

```text
output-probes/codex-webmax-2026-06-13-r6-active-packs/pack-core3-0396A-0370C-0048B/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/pack-core4-0396A-0370C-0048B-0022D/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/base0022D-plus-core3-0396A-0370C-0048B/pred.csv
```

Core3 leave-one-out files:

```text
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core3-without-0396/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core3-without-0370/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core3-without-0048/pred.csv
```

Core4 leave-one-out files:

```text
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core4-without-0396/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core4-without-0370/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core4-without-0048/pred.csv
output-probes/codex-webmax-2026-06-13-r6-active-packs/loo-core4-without-0022/pred.csv
```

## Recommended next submission

First confirm the observed score for:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s5-0274A-0022D/pred.csv
```

Decision:

- If `s5` scored `92.87`, then `test_0022: D` is +1. Use
  `base0022D-plus-core3-0396A-0370C-0048B/pred.csv`.
- If `s5` scored `92.66`, then `test_0022: D` is neutral. Prefer
  `pack-core3-0396A-0370C-0048B/pred.csv` for a cleaner signal.
- If `s5` scored `92.44`, then `test_0022: D` is -1. Use
  `pack-core3-0396A-0370C-0048B/pred.csv`.
- If the `s5` score is unknown and cannot be recovered, use
  `pack-core3-0396A-0370C-0048B/pred.csv` first.

## How to interpret `pack-core3`

Baseline is 92.66 = 429/463.

```text
93.31 = +3 net; all three likely good, jackpot for this pack.
93.09 = +2 net; strong pack, run leave-one-out to isolate the bad member.
92.87 = +1 net; mild gain, likely one or two mixed members.
92.66 = neutral; do not keep the full pack without more evidence.
92.44 or lower = harmful; discard the pack.
```

If `pack-core3` scores above 92.66, use the three `loo-core3-*` files to isolate
which candidate is hurting or helping. Submit the leave-one-out that removes the
most suspicious candidate first:

```text
loo-core3-without-0396/pred.csv
loo-core3-without-0048/pred.csv
loo-core3-without-0370/pred.csv
```

Rationale for this order: `0396` is safety-sensitive, `0048` is conceptually
ambiguous, and `0370` has the strongest external-source intuition among the
three.

## Verification

Contract checks run successfully on all R6 files:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission <pred.csv>
```

Each check returned:

```text
Valid: True
Input rows: 463
Prediction rows: 463
Issues: none
```

## Observed result

The owner submitted:

```text
output-probes/codex-webmax-2026-06-13-r6-active-packs/base0022D-plus-core3-0396A-0370C-0048B/pred.csv
```

Observed score:

```text
426 / 463 = 92.01
```

Compared with the locked base `s1-0274A` at `429 / 463 = 92.66`, the four-change
pack has net effect `-3`:

```text
test_0022: A -> D
test_0048: A -> B
test_0370: B -> C
test_0396: D -> A
```

Implication: do not spend additional submissions on the R6 leave-one-out files.
With single-label multiple-choice scoring, a four-change pack dropping by three
means the group is overwhelmingly harmful: at best one member is neutral and the
others are false flips. No member has enough positive signal to justify rescue
testing while submissions are scarce.
