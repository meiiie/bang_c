# Bang C Harness Architecture

Status: Active
Last updated: 2026-06-08

## Operating Thesis

This project is not a prompt collection. It is a small inference harness with
contracts, configuration, profiling, model invocation, validation, and traceable
development artifacts.

The design follows lessons from:

- Wiii's self-harness and mode/workflow direction;
- Codex-style task harnesses and typed protocol boundaries;
- Odysseus/Goose-style provider inventory and workflow-pack thinking;
- Anthropic's Claude Code large-codebase guidance on working through explicit
  entry points, subproblems, and reusable project context.

Reference:

- https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start

## Architecture

```text
configs/default.json
  -> loader
  -> schema
  -> configurable profiler
  -> prompt strategy
  -> NVIDIA/OpenAI-compatible model client
  -> answer normalizer
  -> optional verifier/tournament
  -> validation summary
  -> pred.csv
```

Runtime modules:

- `config.py`: loads schema-versioned harness config.
- `loader.py`: reads CSV/JSON input and maps it to `Problem`.
- `schema.py`: owns shared dataclasses.
- `classifier.py`: profiles item shape using config markers and thresholds.
- `prompting.py`: builds prompt variants from the profile.
- `nvidia_client.py`: provider boundary.
- `solver.py`: strategy orchestration.
- `normalize.py`: strict answer-letter extraction.
- `evaluation.py`: validates predictions and computes harness score.
- `exporter.py`: writes contest output and dev traces.

## Why Config First

Public test data is not the real problem. Private test can vary by language,
wording, option count, context shape, or question style. Rules that assume one
public-test format are fragile.

The config layer stores:

- input filename candidates;
- output contract;
- model defaults;
- retry/timeout policy;
- multilingual profiling markers;
- classifier thresholds;
- harness scoring weights.

When a new language or question marker appears, update config first. Only change
code when the runtime contract itself needs a new capability.

## Runtime Boundary

Final submission runtime must remain narrow:

```text
read /data
write /output/pred.csv
```

It must not depend on:

- web browsing;
- Wiii backend services;
- database/vector sidecars;
- browser automation;
- subagents;
- local notebooks;
- hidden trace state;
- API keys committed to source.

Development may use those tools to improve the harness, but the final container
must be able to reproduce from source plus the allowed runtime environment.

## Extension Rules

Add a new technique only through one of these extension points:

1. Config marker/threshold/model/rubric update.
2. New prompt variant in `prompting.py`.
3. New profile rule in `classifier.py` backed by config.
4. New strategy in `solver.py`.
5. New validation or scoring check in `evaluation.py`.

Avoid adding cross-cutting branches inside unrelated modules.

## Wiii Reuse Path

If this harness proves useful, Wiii should import the pattern, not the contest
logic:

- schema-versioned workflow config;
- domain-independent profiling contracts;
- strict output validators;
- dev-only trace summaries;
- runtime boundaries that keep UI, tools, memory, and model calls explicit.

