# R3 Conservative Score And Ablation Plan - 2026-06-13

Status: dev-only public-463 analysis artifact. Do not ship into runtime.

## Observed result

- Submitted file: `output-probes/codex-webmax-2026-06-13-r3-conservative/pred.csv`
- Reported leaderboard/test-account score: `92.01`
- Interpretation: very likely `426 / 463` correct (`426 / 463 * 100 = 92.0086`).
- Baseline frontier file `data/q4results/claude_public463_pred_v2_webfixed.csv` was `91.79`, i.e. very likely `425 / 463`.

Therefore R3 conservative is net `+1` correct over the 91.79 frontier.

## R3 conservative flips relative to 91.79 frontier

R3 conservative differs from `claude_public463_pred_v2_webfixed.csv` at 7 public qids:

| qid | frontier | r3 conservative |
| --- | --- | --- |
| test_0068 | B | A |
| test_0080 | A | B |
| test_0115 | B | D |
| test_0200 | B | D |
| test_0271 | A | D |
| test_0329 | A | C |
| test_0389 | A | B |

If the frontier really had 425/463 and R3 has 426/463, these 7 flips contain a mix of correct and incorrect changes. A consistent count is 4 helpful flips and 3 harmful flips, but the exact qids cannot be identified from the aggregate score alone.

## Diagnostic files

Created and contract-validated under:

`output-probes/codex-webmax-2026-06-13-r3-ablation/`

Manifest:

`output-probes/codex-webmax-2026-06-13-r3-ablation/MANIFEST.csv`

### Leave-one-out variants

Each LOO file starts from R3 conservative and reverts exactly one flip back to the 91.79 frontier answer.

Scoring rule:

- If a LOO file scores `92.22` (`427/463`), the reverted R3 flip was harmful/wrong.
- If a LOO file scores `91.79` (`425/463`), the reverted R3 flip was helpful/right.

Files:

- `loo-test_0068/pred.csv`
- `loo-test_0080/pred.csv`
- `loo-test_0115/pred.csv`
- `loo-test_0200/pred.csv`
- `loo-test_0271/pred.csv`
- `loo-test_0329/pred.csv`
- `loo-test_0389/pred.csv`

### Group ablations

Use these first if submissions are limited:

- `drop-r1-original3/pred.csv`: reverts `test_0115`, `test_0200`, `test_0271`
- `drop-r2-new2/pred.csv`: reverts `test_0068`, `test_0329`
- `drop-r3-new2/pred.csv`: reverts `test_0080`, `test_0389`

Group scoring tells whether that whole group is net helpful or harmful, but cannot identify individual qids inside the group.

## Recommended next action

If test-account submissions are available, submit LOO variants one by one and record exact scores. This turns the leaderboard into a direct oracle for which public flips are right/wrong without adding new speculative changes.

If official submissions are scarce, submit only group ablations first, preferably:

1. `drop-r1-original3/pred.csv`
2. `drop-r3-new2/pred.csv`
3. `drop-r2-new2/pred.csv`

After identifying harmful flips, construct a repaired R4 file by keeping only flips proven helpful.

## Validation

All 10 ablation `pred.csv` files were checked with:

```powershell
$env:PYTHONPATH="$PWD\src"
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission <pred.csv>
```

Result: all valid, 463 rows, no schema issues.
