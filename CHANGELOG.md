# Changelog

All notable Neko Core changes are tracked here.

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
