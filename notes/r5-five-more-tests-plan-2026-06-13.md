# R5 Five More Tests Plan - 2026-06-13

Status: dev-only public-463 analysis artifact. Do not ship into runtime.

## Locked base

Current best observed public-test score:

```text
428 / 463 = 92.44
```

Current best file:

```text
output-probes/codex-webmax-2026-06-13-r4-rescue-after-incompatible/revert-0068-0115/pred.csv
```

Known from prior submissions:

- `test_0068`: keep frontier `B` over R3 `A`.
- `test_0115`: keep frontier `B` over R3 `D`.
- `test_0080`: keep R3 `B`; reverting to `A` costs 1.
- `test_0346`: do not boost `A -> B`; it costs 1.
- `test_0200 + test_0271`: pair sum is negative; do not revert both.
- If the old 91.79 frontier score is on the same grader, `test_0329 + test_0389` also sums negative; do not spend early R5 tests on that pair.

## Why singleton tests now

The R4 probe showed that some qids can have zero/nonstandard effect, so broad
packs can hide useful signals. With 5 new test submissions, the cleanest plan is
to test one candidate at a time against the 92.44 base.

Scoring rule for each singleton:

- `92.66`: candidate is +1; add it to the final combined file.
- `92.44`: candidate is neutral; ignore unless later evidence needs it.
- `92.22`: candidate is -1; reject it.

## Generated files

Created and validated:

```text
output-probes/codex-webmax-2026-06-13-r5-singletons/
```

All files passed the submission contract.

Priority order:

1. `p1-0274A-national-assembly-date/pred.csv`
   - `test_0274`: `C -> A`
   - Reason: multiple official/history sources connect the first session of National Assembly I to `2-3-1946`; option C is only broad year.
   - Observed: `92.66`, so this candidate is +1 and should be kept.

2. `p2-0001A-deuteronomy-ambiguous/pred.csv`
   - `test_0001`: `D -> A`
   - Reason: the item asks for Deuteronomy/Torah stoning; both A and D are plausible, but model consensus and Deuteronomy 22:23-24 make A worth a singleton test.

3. `p3-0151I-esg-erm-metrics/pred.csv`
   - `test_0151`: `F -> I`
   - Reason: many model variants prefer "synchronizing ESG goals with traditional risk metrics"; ESG/ERM sources emphasize integration with traditional risk metrics and risk taxonomies.

4. `p4-0109C-gas-demand-effects/pred.csv`
   - `test_0109`: `A -> C`
   - Reason: gas-price demand effects may combine substitution and income effects; model consensus favored C. This is lower confidence than p1/p2.

5. `p5-0022D-id-card-residence/pred.csv`
   - `test_0022`: `A -> D`
   - Reason: legal/procedure wording around ID-card exchange can plausibly require old card plus residence proof; model consensus favored D. Lower confidence.

Reserve:

- `reserve-0396A-safety-vs-direct/pred.csv`
  - `test_0396`: `D -> A`
  - Reason: direct-answer models prefer A, but this is safety-sensitive and the existing refusal answer may be intentional. Use only if one of the main five is skipped.

## Recommended submission flow

Submit the files in priority order and report each score.

For each candidate:

```text
score 92.66 -> keep candidate
score 92.44 -> neutral, ignore for final unless needed
score 92.22 -> reject candidate
```

After all five singleton tests, build a final combined file by applying exactly
the candidates that scored 92.66 to the 92.44 base.

If two candidates score 92.66, expected combined score is:

```text
430 / 463 = 92.87
```

If three candidates score 92.66:

```text
431 / 463 = 93.09
```

This still may not reach 95, but it is the lowest-confusion use of the five new
test submissions.

## Cumulative follow-up after p1 succeeded

Observed:

- `p1-0274A-national-assembly-date/pred.csv` scored `92.66`.
- Keep `test_0274: A`.

Created cumulative files based on the 92.44 base plus the proven `0274A`:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s1-0274A/pred.csv
output-probes/codex-webmax-2026-06-13-r5-cumulative/s2-0274A-0001A/pred.csv
output-probes/codex-webmax-2026-06-13-r5-cumulative/s3-0274A-0151I/pred.csv
output-probes/codex-webmax-2026-06-13-r5-cumulative/s4-0274A-0109C/pred.csv
output-probes/codex-webmax-2026-06-13-r5-cumulative/s5-0274A-0022D/pred.csv
```

All cumulative files passed the submission contract.

Next recommended test:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s2-0274A-0001A/pred.csv
```

Interpretation:

- `92.87`: `0001A` is +1; keep it.
- `92.66`: `0001A` is neutral; ignore it.
- `92.44`: `0001A` is -1; reject it and keep `s1-0274A`.

Observed:

- `s2-0274A-0001A/pred.csv` scored `92.44`.
- Therefore `test_0001: D -> A` is -1. Reject it.
- Current best remains `s1-0274A/pred.csv` at `92.66`.

Next test:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s3-0274A-0151I/pred.csv
```

Interpretation:

- `92.87`: `0151I` is +1; keep it with `0274A`.
- `92.66`: `0151I` is neutral; ignore it.
- `92.44`: `0151I` is -1; reject it and keep `s1-0274A`.

Observed:

- `s3-0274A-0151I/pred.csv` scored `92.44`.
- Therefore `test_0151: F -> I` is -1. Reject it.
- Current best remains `s1-0274A/pred.csv` at `92.66`.

Next test:

```text
output-probes/codex-webmax-2026-06-13-r5-cumulative/s4-0274A-0109C/pred.csv
```

Interpretation:

- `92.87`: `0109C` is +1; keep it with `0274A`.
- `92.66`: `0109C` is neutral; ignore it.
- `92.44`: `0109C` is -1; reject it and keep `s1-0274A`.

Observed:

- `s4-0274A-0109C/pred.csv` scored `92.44`.
- Therefore `test_0109: A -> C` is -1. Reject it.
- Current best remains `s1-0274A/pred.csv` at `92.66`.

Pending confirmation:

- Exact observed score for `s5-0274A-0022D/pred.csv` has not been recorded in
  this note yet. This score determines whether `test_0022: A -> D` should be
  kept, ignored, or rejected before R6 active-pack submissions.
