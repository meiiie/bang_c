# Neko Core — Engineering Notebook

Working notes, investigations, and lessons learned while developing Neko Core for
HackAIthon 2026 Bảng C. This is a **development journal**, not contest-runtime code:
nothing here ships in the Docker container.

## Conventions

- One dated file per investigation: `YYYY-MM-DD-<topic>.md`.
- Every claim about behavior must cite **evidence** (file:line, a trace number, a
  command output) — we do not assert from memory or from second-hand opinion.
- When a colleague/reviewer gives feedback, we **verify each point against the code
  and real run data before accepting it** (karpathy guideline: don't assume).
- `lessons.md` is the running list of durable lessons (append-only).

## Index

- [**▶ RESUME-HERE.md**](RESUME-HERE.md) — **start here**: current state, the model-access
  blocker, and the exact ordered steps to resume.

- [2026-06-10 — Baseline 85.53 diagnosis](2026-06-10-baseline-85.53-diagnosis.md) —
  why the public-test score is 85.53; evidence-backed root causes (fake confidence,
  diacritic-collision routing, reasoning-suppressed prompts, overfit adjudicators).
- [2026-06-10 — Architecture proposal](2026-06-10-architecture-proposal.md) —
  non-overfit, multilingual-robust, calibrated redesign + 4-phase roadmap + how
  Claude Code's harness informs it. **Ready to execute.**
- [worklog.md](worklog.md) — append-only execution journal.
- [session-2026-06-12.md](session-2026-06-12.md) — consolidated session report (measured results).
- [mtp-measured-2026-06-13.md](mtp-measured-2026-06-13.md) · [router-tir-measured-2026-06-13.md](router-tir-measured-2026-06-13.md) · [public-test-composition-2026-06-11.md](public-test-composition-2026-06-11.md) — key measured analyses.
- [mtp-packaging-session-2026-06-14.md](mtp-packaging-session-2026-06-14.md) — image packaging session + lessons.
- [lessons.md](lessons.md) — durable lessons.
- `../docs/method-writeup.md` — contest method write-up (Ý tưởng 10 pts), DRAFT.

## Standing constraints (do not violate)

- Models: **Gemma-4** and **Qwen3.5 ≤9B** only; embed/rerank **BGE-m3 / Qwen-Rerank**.
- Final container: offline, self-contained, no web/subagents/db. Read `/data`, write
  `/output/pred.csv` (`qid,answer`, per-row letters — never hard-code A–D).
- Private test = **2000 questions, multilingual & diverse** (VI/EN/KO/ZH/math/…).
  Anything that only works for Vietnamese or only for the 463 public questions is a
  liability. **Do not overfit.**
- Config-first, no god files, every change ships with a verification story
  (`AGENTS.md`).
