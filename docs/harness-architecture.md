# Neko Core Harness Architecture

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
- A local historical Claude Code source snapshot at
  `E:\Sach\Sua\test\claude_lo\claude-code`, studied for architectural patterns
  only. Do not copy proprietary implementation code into this repository.

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
  -> dev trace/session artifacts
```

Runtime modules:

- `branding.py`: owns Neko Core identity, version string, and ASCII banner.
- `capabilities.py`: lists runtime and development-only capabilities in one
  registry.
- `doctor.py`: runs lightweight diagnostics similar to CLI doctor/status
  workflows.
- `project.py`: initializes project-local configuration under `.neko-core/`
  so teams can tune workflows and markers without editing source files.
- `workflows.py`: resolves named workflow profiles from config.
- `scripts/verify.ps1`: dev-only verification runner that emits
  command/output/result evidence and a final verdict.
- `scripts/evaluate.ps1`: dev-only workflow comparison runner for stability,
  trace review, trace comparison, harness-score review, and eval summary
  artifacts.
- `compare.py`: compares two trace-enabled runs using manifests and prediction
  trace rows.
- `config.py`: loads schema-versioned harness config.
- `loader.py`: reads CSV/JSON input and maps it to `Problem`.
- `manifest.py`: writes reproducible run metadata for trace-enabled runs.
- `schema.py`: owns shared dataclasses.
- `classifier.py`: profiles item shape using config markers and thresholds.
- `prompting.py`: builds prompt variants from the profile.
- `nvidia_client.py`: provider boundary.
- `solver.py`: strategy orchestration.
- `normalize.py`: strict answer-letter extraction.
- `evaluation.py`: validates predictions and computes harness score.
- `exporter.py`: writes contest output and dev traces.
- `review.py`: reads dev traces after a run and reports reviewer findings
  without invoking a model.

Dev traces are structured as agent steps on each prediction. Current roles are
`classifier`, `solver`, `repair`, `verifier`, and `synthesizer`. This gives the
team a Claude Code-like review timeline without changing the contest artifact:
`pred.csv` remains only `qid,answer`.

Trace review is intentionally separate from solving. `--review-trace` can be
run after any trace-enabled workflow to catch low confidence, fallback paths,
trace warnings, missing roles, and blocked steps. This mirrors the
execute-then-verify split from coding agents while keeping the contest runtime
simple.

Run manifests are written as `run-manifest.json` only for trace-enabled
development runs. They capture config/input hashes and selected runtime options,
so experiments can be compared without relying on memory or hidden local state.
`--compare-traces` uses those manifests plus prediction trace rows to flag
changed answers, input/config drift, confidence drift, and fallback drift.

`--run-dir <path>` creates a development run session. The CLI writes
`output/pred.csv`, `traces/`, and `run-report.md` under that directory, then
runs the trace reviewer against the session trace. This gives the team one
portable folder per experiment while keeping the final `/data` to `/output`
contest contract unchanged.

`scripts/evaluate.ps1` composes those run sessions into a higher-level eval
session. Each workflow repeat gets its own run folder, then the eval report
records trace review, trace comparison, and a selected candidate. This mirrors
the agent pattern of separating execution, verification, and synthesis.

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

`neko-core --init` copies the canonical config to `.neko-core/config.json`.
When no `--config` path is provided, the loader checks this project-local
config before `configs/default.json`. This mirrors agent CLI practice: runtime
source stays stable while a team can tune local harness profiles.

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

## Claude Code Patterns Adapted

Useful patterns from the local Claude Code snapshot:

- Keep the bootstrap/entrypoint thin and fast.
- Put commands such as version, doctor, and status before the expensive solve
  path.
- Treat tool/workflow registries as explicit capability lists, not scattered
  conditionals.
- Separate diagnostics, runtime execution, and UI rendering.
- Use feature/config gates for optional capabilities instead of hard-coding
  private-test assumptions.

For Neko Core, the first adapted slices are `--doctor`, `--capabilities`,
`--list-workflows`, `scripts/verify.ps1`, and `scripts/evaluate.ps1`. They prove
config, contract, model, key presence, input discovery, the
runtime/development boundary, verification evidence, and workflow stability
without running inference unless explicitly requested. Future work should add
subagent-style evaluation reviewers in the same style, while keeping the final
Docker contract narrow.

## Wiii Reuse Path

If this harness proves useful, Wiii should import the pattern, not the contest
logic:

- schema-versioned workflow config;
- domain-independent profiling contracts;
- strict output validators;
- dev-only trace summaries;
- runtime boundaries that keep UI, tools, memory, and model calls explicit.
