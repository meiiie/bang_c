# Changelog

All notable Neko Core changes are tracked here.

## 0.5.0 - 2026-06-11

- Added chain-of-thought reasoning as the contest path (`self-consistency` workflow):
  the model reasons step by step, then the option letter is extracted. Validated on the
  real `Gemma-4-26B-A4B-Q4` GGUF — public leaderboard **87.26** vs **77.11** for the
  letter-only baseline on the same model (+10.15), and above the prior 85.53.
- Fixed chain-of-thought truncation: raised `reasoning_max_tokens` 512 -> 2048. At 512 the
  reasoning was cut before the answer line, causing ~30% invalid-output fallbacks and wrong
  answers on calculation/reading items.
- Added agreement-based confidence calibration (`calibration.py`) to replace hard-coded
  per-strategy confidence. Set `self_consistency_samples` default to 1 (single
  deterministic CoT); k>1 is identical at temperature 0, so it only adds cost.
- Added a cross-model challenger strategy (`solve_with_challenge`) that escalates only
  low-agreement items to an independent model (config-gated; CLI wiring deferred).
- Made routing language-agnostic and less overfit: calculation routing now requires a real
  quantitative signal (operator/number+unit/two numbers) instead of a topic word plus a
  stray digit; added multilingual negation cues (KO/ZH/JA/EN); kept Vietnamese diacritics;
  hardened answer extraction for natural CoT endings ("the answer is A", "Answer: (C)").
- Added a multilingual gold-suite fixture (VI/EN/KO/ZH/FR/DE/ES/RU/AR/TH, 6+ scripts) and
  tests for self-consistency, calibration, normalization, and routing (109 tests total).
- Defaulted the self-contained Gemma image to the reasoning workflow
  (`Dockerfile.gemma-local`, `docker/neko-entrypoint.sh`); published candidate image
  `hacamy12345/neko-core:gemma26b-q4-cot-20260610`.
- Added method write-ups (`docs/method-writeup.md`, `docs/method-writeup-vi.md`) and an
  engineering notebook under `notes/`.

## 0.4.0 - 2026-06-09

- Added bounded autonomous `neko core --yolo` mode for strict contest runs with
  checkpointing, auto-resume, policy enforcement, and review artifacts.
- Added `--check-submission` to validate the final `pred.csv` name, header,
  qids, row count, and per-row answer alphabet without hard-coding A-D.
- Added submission readiness documentation after the website accepted the
  corrected `pred.csv` artifact and confirmed the older sample/upload artifact
  was not a reliable source of truth.
- Tightened CSV export to UTF-8 without BOM and LF line endings.
- Expanded adjudication, retry, resume, and contract tests for the current
  public-test development corpus.

## 0.3.1 - 2026-06-09

- Added pipx-based one-command installers for Windows and Unix shells.
- Packaged the default harness config so `neko-core` works outside the repo.
- Added release workflow for tests, Python artifacts, Docker CSV verification,
  and optional Docker Hub publishing.
- Added fail-closed runtime validation for Bang C model-family rules.
- Added `contest-strict` workflow with verifier repair and checkpoint-friendly
  long-run usage.

## 0.3.0 - 2026-06-08

- Added config-first Neko Core harness for HackAIthon 2026 Bang C.
- Added CLI registries for workflows, agents, tools, commands, and policy.
- Added trace review, checkpoint/resume, run sessions, and Docker contract
  verification.
