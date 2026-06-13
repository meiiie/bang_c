# Adjudicated self-consistency candidate - 2026-06-13

Status: development-only candidate, not promoted to contest default.

## Why

Leaderboard target moved from the current 88.55 band to at least the 89.63 band. MTP helps Vong-2 time score, but it cannot improve accuracy. This candidate keeps the same Gemma model call count as single-sample self-consistency, then applies a small set of deterministic adjudicators for formula/principle cases.

## Implementation

- New workflow: `adjudicated-self-consistency`
- New strategy: `adjudicated_self_consistency`
- Production/default adjudicators remain unchanged by default.
- Experimental rules are reachable only through `include_experimental=True`, called only by `_apply_deterministic_adjudicators()` from the explicit candidate strategy.
- Added guard tests so experimental rules stay silent outside their narrow domain.

Experimental rule families kept:

- induction motor slip speed when the problem explicitly asks for speed
- chiral selectivity ratio when the formula is stated in the prompt
- PMMC all-true advantages only when every non-all choice is a known true advantage
- common two-wattmeter wording for three-phase three-wire unbalanced power
- Keynesian actual-vs-planned saving mismatch -> inventory adjustment

Experimental rule families rejected after review:

- whistleblower direct-report: too close to one public scenario and normatively
  contestable;
- price-change "first mechanism": economics decomposition can be argued as
  simultaneous, so forcing substitution first is not deterministic enough.
- remaining recoverable public-463 candidates such as urbanization doctrine,
  Buddhist "Phap bao", Vietnam north-south geography, CTC passage stance,
  eSIM price evidence, trustworthiness tautology, and the garbled eigenvalue
  matrix: not safe as deterministic adjudicators without public-test overfit.
  A triangular-matrix eigenvalue rule is only acceptable for well-formed
  matrices, and does not recover the corrupted public item.

## Local evidence

Read-only pseudo-reference simulation against the stored public-463 artifacts:

- baseline agreement: `432/463 = 93.30%`
- candidate agreement: `438/463 = 94.60%`
- delta: `+6`
- losses: `0`

This is a selection signal, not leaderboard proof. The real test is one GPU run on the public 463 with the local Gemma 26B Q4 setup, followed by normal submission only if the owner approves.

## Verification

Completed locally:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests -v
python -m compileall -q src
python -m hackaithon_c.run --policy
git diff --check
```

Latest result after adding preflight/MTP readiness tests, workflow replay coverage, the measured-run gate, the Keynesian guard, MTP script static regressions, contest-artifact hygiene guards, guarded GPU scripts for both accuracy and MTP, the development workflow/strategy opt-in gate, GPU-script portability guards, prediction-pool analysis, and experiment assessment gates: `255` tests passed; policy PASS; compile PASS; diff-check PASS with CRLF warnings only.

Wrapper contract check also completed through `.\neko-core.ps1`:

```powershell
.\neko-core.ps1 --help
.\neko-core.ps1 --doctor
.\neko-core.ps1 --capabilities
.\neko-core.ps1 --list-workflows
.\neko-core.ps1 --policy
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output-contract-check --trace-dir traces-contract-check --dry-run
.\neko-core.ps1 --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --check-submission output-contract-check\pred.csv
.\neko-core.ps1 --review-trace traces-contract-check
.\neko-core.ps1 --compare-traces traces-contract-check traces-contract-check
.\neko-core.ps1 --review-tasks traces-contract-check --run-dir run-contract-check
```

Results: doctor OK with expected local-dev warnings for missing `/models/...`
and `/data`; dry-run covered `463/463`, wrote valid `pred.csv`, submission
check passed with no issues, trace comparison passed with changed answers `0`,
and review-task generation succeeded. `review-trace` returned WARN due dry-run
low-confidence heuristic predictions, which is expected and not a contract
failure.

Added deterministic preflight script:

```powershell
$env:PYTHONPATH = "$PWD/src"
python scripts/analyze_adjudicated_candidate.py `
  --input "C:\Users\Admin\Downloads\public-test_1780368312.json" `
  --baseline data/q4results/gemma26_safety_probe.csv `
  --reference data/q4results/claude_public463_pred_v2_webfixed.csv `
  --summary-json notes/adjudicated-self-consistency-public463-preflight-2026-06-13.json `
  --fail-on-loss `
  --workflow-replay
```

Preflight artifact: `notes/adjudicated-self-consistency-public463-preflight-2026-06-13.json`.
It confirms `candidate_changes=6`, `fixes=6`, `losses=0`, experimental-rule isolation `ok=true`, and solver replay `ok=true`.

Added prediction-pool analyzer:

```powershell
$env:PYTHONPATH = "$PWD/src"
python scripts/analyze_prediction_pool.py `
  --input "C:\Users\Admin\Downloads\public-test_1780368312.json" `
  --baseline data/q4results/gemma26_safety_probe.csv `
  --reference data/q4results/claude_public463_pred_v2_webfixed.csv `
  --candidate 31b=data/q4results/31bq4_public463_pred.csv `
  --candidate gemma31_safety=data/q4results/gemma31_safety_probe.csv `
  --candidate q6=data/q4results/gemma26_Q6_K.csv `
  --candidate q8=data/q4results/gemma26_Q8_0.csv `
  --candidate sweep768=data/q4results/gemma26_sweep_768.csv `
  --candidate sweep1280=data/q4results/gemma26_sweep_1280.csv `
  --candidate sweep2048=data/q4results/gemma26_sweep_2048.csv `
  --summary-json notes/_prediction_pool_public463_gemma_variants_2026-06-13.json
```

Gemma-variant pool result against the same pseudo-reference:

- baseline agreement: `432/463 = 93.30%`
- best single existing variant: `gemma31_safety`, delta `0`; every other single variant is negative
- pool oracle: `+22`, showing useful signal exists but needs a safe selector
- majority with baseline tie-break: `+1`
- non-baseline consensus threshold 7: `+3`
- adjudicated candidate remains best single at `+6`; a one-off check of
  adjudicated plus threshold-7 consensus reached `+7` but introduced one proxy
  loss and depends on stored public-run variants, so it is analysis-only, not a
  clean runtime/shipping path.

Conclusion: do not promote public-prediction fusion. Keep the candidate path as
measured `adjudicated-self-consistency`; use the pool analyzer to judge future
measured candidates and to decide whether a real router/TIR run has enough
headroom to justify GPU time.

Added measured-run gate script:

```powershell
$env:PYTHONPATH = "$PWD/src"
python scripts/compare_candidate_predictions.py `
  --input "C:\Users\Admin\Downloads\public-test_1780368312.json" `
  --baseline data/q4results/gemma26_safety_probe.csv `
  --candidate path\to\candidate\pred.csv `
  --reference data/q4results/claude_public463_pred_v2_webfixed.csv `
  --fail-on-loss `
  --min-delta 1 `
  --summary-json notes/adjudicated-self-consistency-measured-gate.json
```

Use this only on a measured candidate `pred.csv`; it does not call a model.
This gate proves contract-validity and no-regression against the proxy
pseudo-reference only. It is not an accuracy proof, because the reference is
not the contest grader. For a real public-463 candidate, promotion requires
contract-valid output, no losses against the pseudo-reference gate, positive
measured delta as a selection signal, and owner approval before any submission
decision.

Added experiment assessment script:

```powershell
python scripts/assess_experiment_results.py `
  --accuracy-summary path\to\measured-gate.json `
  --min-accuracy-delta 1 `
  --max-accuracy-losses 0 `
  --summary-json path\to\experiment-assessment.json
```

This script reads measured artifacts only. It does not call a model, write
`pred.csv`, submit, or change runtime behavior. `run_adjudicated_candidate.sh`
now calls it automatically after the proxy no-regression gate and writes
`experiment-assessment.json`; a PASS means "ready for owner review", not
"auto-submit".

Claude Code review:

- First review caught that experimental rules were leaking into production adjudicator paths.
- Fixed by splitting production and experimental registries.
- Second review confirmed previous blockers were fixed and only requested a speed-target guard for the induction rule.
- Added the guard and a negative test.
- Third review confirmed workflow replay no longer swallows solver errors and the overlay mirrors date/direct evidence adjudicators; no blocking, high, or medium findings remain.
- Fourth review found no additional safe deterministic rule to add from the
  remaining recoverable disagreements; recommendation is to stop the adjudicator
  layer at the current +6 candidate and use measured CoT/router runs for any
  further accuracy chase.
- Fifth review found two medium issues in the measured-run gate (multi-letter
  answer validation and no-op gates without a reference). Both were fixed and
  re-reviewed with no remaining blocking, high, or medium findings.
- Sixth review found one hygiene issue: public-test scratch artifacts under
  `notes/_*` and proxy preflight JSON were not ignored. `.gitignore` now keeps
  those answer-bearing development artifacts out of commits. The same review
  also requested clearer wording that the measured gate is proxy/no-regression
  evidence, not grader truth; this note now states that explicitly.
- A follow-up Codex explorer found `.dockerignore` did not mirror the same
  sensitive-artifact exclusions. `.dockerignore` now blocks the same scratch,
  run, trace, data, model, and proxy-gate artifacts from remote/Kaniko-style
  build contexts. Regression tests also guard the ignore patterns and prevent
  runtime/config/test sources from embedding concrete leaderboard observations.
- The measured GPU run is now wrapped by `scripts/gpu/run_adjudicated_candidate.sh`.
  It refuses to run unless `OWNER_SIGNOFF=1`, records `launch-config.json`,
  runs the candidate workflow with checkpointing through the explicit
  `--allow-development-workflow` gate, validates `pred.csv`, and then calls
  `scripts/compare_candidate_predictions.py` with `--fail-on-loss` and
  `--min-delta`, followed by `scripts/assess_experiment_results.py` to produce
  an owner-review assessment. The launch config includes git commit/dirty
  count, script SHA-256, and model file size. It contains no
  submission/push/network step.
  The script now defaults `REPO_DIR` from its own location, so it can be launched
  from outside the repo on a pod without silently resolving baselines or source
  paths relative to the caller's current directory.
- Non-dry-run workflows marked `phase=development`, and direct CLI selection of
  development-only strategies, now require `--allow-development-workflow` or
  `HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1`. This keeps unmeasured candidates out of
  the final runtime path while leaving `quick-dry-run` contract smoke available.

## GPU command after owner sign-off

Do not run this until GPU spend is explicitly approved.

```bash
export OWNER_SIGNOFF=1
export INPUT_PATH=/workspace/public-test_1780368312.json
export MODEL_PATH=/workspace/models/gemma-4-26B_q4_0-it.gguf
export BASELINE_PATH=/workspace/bang_c/data/q4results/gemma26_safety_probe.csv
export REFERENCE_PATH=/workspace/bang_c/data/q4results/claude_public463_pred_v2_webfixed.csv
export REPO_DIR=/workspace/bang_c
bash /workspace/bang_c/scripts/gpu/run_adjudicated_candidate.sh
```

Promotion rule: only promote or submit if the measured public-463 output is net-positive against the current submitted baseline and the owner approves the submission.

## Local verification smoke

Command run on 2026-06-13:

```powershell
.\scripts\verify.ps1 -InputPath "C:\Users\Admin\Downloads\public-test_1780368312.json"
```

Result: `VERDICT: PASS` / exit code `0`.

Scope note: this is a local harness smoke check. The workflow portions use
`quick-dry-run --limit 3`, validate run/session/trace/review-task plumbing, and
confirm contract artifacts can be produced and resumed. It is not an accuracy
measurement and does not imply any leaderboard score.

## Development gate hardening

Follow-up on 2026-06-13: the CLI now gates development-only strategies using
the resolved strategy value, not only the raw `--strategy` argument. This means
a future workflow accidentally marked `phase=runtime` but pointing at
`router`, `tir`, `adjudicated_self_consistency`, or another development-only
strategy still fails closed unless `--allow-development-workflow` or
`HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1` is set.

Verification:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest tests.test_contract.ContestContractTest.test_direct_development_strategy_requires_explicit_allow tests.test_contract.ContestContractTest.test_resolved_development_strategy_requires_explicit_allow_even_if_workflow_phase_is_wrong tests.test_contract.ContestContractTest.test_non_dry_development_workflow_requires_explicit_allow tests.test_contract.ContestContractTest.test_dry_development_workflow_remains_available_for_contract_smoke -v
python -m hackaithon_c.run --policy
python -m compileall -q src tests scripts
git diff --check
python -m unittest discover -s tests -v
```

Results: targeted gate tests pass, policy `PASS`, compileall pass,
`git diff --check` pass with CRLF warnings only, and full unittest pass
(`261` tests).
