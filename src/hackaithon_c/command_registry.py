from __future__ import annotations

from dataclasses import dataclass

from .config import HarnessConfig


@dataclass(frozen=True)
class CommandSpec:
    name: str
    phase: str
    category: str
    option: str
    description: str
    example: str
    guardrail: str


def list_commands(config: HarnessConfig) -> tuple[CommandSpec, ...]:
    output_file = config.output_file
    return (
        CommandSpec(
            name="version",
            phase="cli",
            category="identity",
            option="--version",
            description="Print the Neko Core version without running inference.",
            example="neko --version",
            guardrail="Fast path; no file, model, or network access.",
        ),
        CommandSpec(
            name="banner",
            phase="cli",
            category="identity",
            option="--banner",
            description="Print the ASCII Neko Core brand banner.",
            example="neko --banner",
            guardrail="Brand preview only; does not change config or outputs.",
        ),
        CommandSpec(
            name="init",
            phase="cli",
            category="configuration",
            option="--init",
            description="Create a project-local .neko-core/config.json profile.",
            example="neko --init",
            guardrail="Keeps source config stable; use --force only when resetting local config intentionally.",
        ),
        CommandSpec(
            name="doctor",
            phase="cli",
            category="diagnostics",
            option="--doctor",
            description="Check environment, config, input discovery, and output contract.",
            example="neko --doctor --input C:\\data\\public_test.json",
            guardrail="Diagnostics only; does not call the model or write predictions.",
        ),
        CommandSpec(
            name="capabilities",
            phase="cli",
            category="registry",
            option="--capabilities",
            description="Show runtime, CLI, and development capabilities.",
            example="neko --capabilities",
            guardrail="Read-only registry surface.",
        ),
        CommandSpec(
            name="agents",
            phase="cli",
            category="registry",
            option="--agents / --agent",
            description="Show harness role boundaries and one-role details.",
            example="neko --agent task-resolver",
            guardrail="Read-only role registry; does not spawn subagents.",
        ),
        CommandSpec(
            name="tools",
            phase="cli",
            category="registry",
            option="--tools / --tool",
            description="Show tool contracts, permission class, inputs, outputs, and guardrails.",
            example="neko --tool web-research",
            guardrail="Read-only tool registry; external tools stay quarantined from runtime output.",
        ),
        CommandSpec(
            name="commands",
            phase="cli",
            category="registry",
            option="--commands / --command",
            description="Show this command registry and one-command details.",
            example="neko --command run",
            guardrail="Read-only command registry; useful before running heavier workflows.",
        ),
        CommandSpec(
            name="policy",
            phase="cli",
            category="diagnostics",
            option="--policy",
            description="Audit runtime/development boundaries across commands, tools, and agents.",
            example="neko --policy",
            guardrail="Read-only audit command; the solve path enforces the same policy gate.",
        ),
        CommandSpec(
            name="workflows",
            phase="cli",
            category="registry",
            option="--list-workflows / --workflow",
            description="List configured workflow profiles or run one by name.",
            example="neko --workflow quick-dry-run --input C:\\data\\public_test.json --limit 5",
            guardrail="Runtime workflows remain config-defined instead of source-hardcoded.",
        ),
        CommandSpec(
            name="model-inventory",
            phase="development",
            category="provider",
            option="--model-inventory",
            description="Probe provider models and filter Bang C eligible families.",
            example="neko --model-inventory --run-dir run-model-inventory",
            guardrail="Provider metadata only; does not send contest questions.",
        ),
        CommandSpec(
            name="profiles",
            phase="runtime",
            category="config",
            option="--profiles",
            description="Print configured runtime profiles and the active profile.",
            example="neko --profiles",
            guardrail="Read-only; use --profile or HACKC_PROFILE to select one run.",
        ),
        CommandSpec(
            name="yolo",
            phase="runtime",
            category="autonomy",
            option="--yolo",
            description="Run the bounded autonomous contest preset.",
            example="neko core --yolo --data-dir /data --output-dir /output --run-dir /output/neko-run",
            guardrail=(
                "Sets contest-strict, checkpointing, auto-resume, and review artifacts; "
                "does not bypass policy, submit results, delete files, or use development-only tools."
            ),
        ),
        CommandSpec(
            name="run",
            phase="runtime",
            category="contest",
            option="--input / --data-dir / --output-dir",
            description=f"Read contest input, solve problems, and write {output_file}.",
            example="neko --workflow contest-auto --data-dir /data --output-dir /output",
            guardrail="Final path writes only the configured qid,answer prediction CSV.",
        ),
        CommandSpec(
            name="run-session",
            phase="development",
            category="experiment",
            option="--run-dir / --resume / --auto-resume / --checkpoint-every",
            description="Create or resume a portable run folder with output, traces, report, tasks, events, and checkpoints.",
            example="neko --workflow quick-dry-run --input C:\\data\\public_test.json --run-dir run-smoke --limit 5 --auto-resume",
            guardrail="Checkpoint artifacts stay in the trace folder; final pred.csv is written only after validation.",
        ),
        CommandSpec(
            name="sessions",
            phase="development",
            category="resume",
            option="--list-runs / --session / --events",
            description="Rediscover local run sessions and render resume-ready state.",
            example="neko --session run-smoke",
            guardrail="Read-only session inspection; no hidden state required.",
        ),
        CommandSpec(
            name="trace-review",
            phase="development",
            category="verification",
            option="--review-trace / --review-tasks / --compare-traces",
            description="Review trace artifacts, create qid tasks, and compare runs.",
            example="neko --review-tasks run-smoke\\traces --run-dir run-review-tasks",
            guardrail="Review outputs are evidence; they do not mutate pred.csv.",
        ),
        CommandSpec(
            name="check-submission",
            phase="cli",
            category="verification",
            option="--check-submission",
            description="Validate a pred.csv artifact against input qids, header, filename, and per-row allowed letters.",
            example="neko --input C:\\data\\public_test.csv --check-submission pred.csv",
            guardrail="Read-only artifact check; validates allowed letters from each input row instead of hard-coding A-D.",
        ),
        CommandSpec(
            name="resolve-tasks",
            phase="development",
            category="verification",
            option="scripts/resolve-tasks.ps1",
            description="Rerun qid-scoped review tasks and record before/after evidence.",
            example=".\\scripts\\resolve-tasks.ps1 -TaskPath run-review-tasks\\review-tasks.json -InputPath C:\\data\\public_test.json -Workflow verify-all",
            guardrail="Scoped by qid to avoid broad answer churn.",
        ),
        CommandSpec(
            name="verify",
            phase="development",
            category="verification",
            option="scripts/verify.ps1",
            description="Run the local verification harness and print command/output evidence.",
            example=".\\scripts\\verify.ps1 -InputPath C:\\data\\public_test.json",
            guardrail="Development-only; validates the harness without changing source.",
        ),
        CommandSpec(
            name="evaluate",
            phase="development",
            category="eval",
            option="scripts/evaluate.ps1",
            description="Run workflow comparisons and synthesize eval reports.",
            example=".\\scripts\\evaluate.ps1 -InputPath C:\\data\\public_test.json -Limit 10",
            guardrail="Eval artifacts inform changes; final runtime remains narrow.",
        ),
        CommandSpec(
            name="runpod-gpu-shortlist",
            phase="development",
            category="infrastructure",
            option="scripts/runpod-gpu-shortlist.ps1",
            description="List RunPod GPU candidates from account metadata without creating pods.",
            example=".\\scripts\\runpod-gpu-shortlist.ps1 -MinMemoryGB 48",
            guardrail="Read-only infrastructure metadata; requires RUNPOD_API_KEY outside git and does not spend money.",
        ),
    )


def resolve_command(config: HarnessConfig, name: str) -> CommandSpec:
    commands = {command.name: command for command in list_commands(config)}
    if name not in commands:
        available = ", ".join(commands) or "none"
        raise ValueError(f"Unknown command '{name}'. Available commands: {available}")
    return commands[name]


def render_commands(commands: tuple[CommandSpec, ...]) -> str:
    lines = ["Neko Core commands"]
    for command in commands:
        lines.append(
            f"[{command.phase}] {command.name}: {command.option} - {command.description}"
        )
    return "\n".join(lines)


def render_command_detail(command: CommandSpec) -> str:
    return "\n".join(
        (
            "Neko Core Command",
            f"Name: {command.name}",
            f"Phase: {command.phase}",
            f"Category: {command.category}",
            f"Option: {command.option}",
            f"Description: {command.description}",
            "",
            "Example:",
            f"- {command.example}",
            "",
            "Guardrail:",
            f"- {command.guardrail}",
        )
    )
