# AGENTS.md

Status: Active

Owner: Bang C competition team

Last updated: 2026-06-08

## Purpose

This repository is a competition inference harness for HackAIthon 2026 Bang C.
It must stay clean, reproducible, and reusable as an AI-core research artifact.

The harness is more important than any single prompt. Treat model calls,
profiling, prompting, validation, tracing, Docker packaging, and documentation
as one system.

## Core Rules

- Do not hard-code public-test answers, qids, leaderboard observations, or
  private-test assumptions.
- Do not assume the private test language is Vietnamese. The input may contain
  English, French, Spanish, Vietnamese, mixed-language content, or translated
  variants.
- Keep data-dependent markers, thresholds, model defaults, and rubric weights in
  `configs/default.json` or another explicit config file.
- Keep runtime source modular. Avoid god files. Prefer small modules with clear
  contracts: loader, config, profiler/classifier, prompt builder, solver,
  normalizer, evaluator, exporter.
- The final container path must read `/data`, write `/output/pred.csv`, and not
  depend on web browsing, Wiii Core, databases, browsers, subagents, local
  notebooks, or hidden state.
- Web research, subagents, and manual analysis are allowed during development,
  but they must only improve config, tests, prompts, and docs.
- Never commit API keys, `.env`, generated outputs, trace logs, public/private
  answer files, or leaderboard-derived hacks.
- Every harness change must include a verification story: unit test, dry-run
  contract check, Docker smoke, or documented reason why not.

## Architecture Standard

Use a layered workflow:

```text
input contract
  -> schema normalization
  -> configurable profiling
  -> prompt strategy selection
  -> model invocation
  -> answer normalization
  -> optional verifier/tournament
  -> contract validation
  -> pred.csv export
  -> dev-only trace and run summary
```

Adding a new technique should normally mean adding one focused module or config
entry, not changing unrelated layers.

## Verification Commands

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m unittest discover -s tests -v
python -m compileall -q src
python -m hackaithon_c.run --input "C:\Users\Admin\Downloads\public-test_1780368312.json" --output-dir output-dryrun --trace-dir traces-dryrun --dry-run
docker build -t bang-c:dev .
```

For model smoke tests, set `NVIDIA_API_KEY` outside git first.

