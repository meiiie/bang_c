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
            example=".\\neko-core.ps1 --version",
            guardrail="Fast path; no file, model, or network access.",
        ),
        CommandSpec(
            name="banner",
            phase="cli",
            category="identity",
            option="--banner",
            description="Print the ASCII Neko Core brand banner.",
            example=".\\neko-core.ps1 --banner",
            guardrail="Brand preview only; does not change config or outputs.",
        ),
        CommandSpec(
            name="init",
            phase="cli",
            category="configuration",
            option="--init",
            description="Create a project-local .neko-core/config.json profile.",
            example=".\\neko-core.ps1 --init",
            guardrail="Keeps source config stable; use --force only when resetting local config intentionally.",
        ),
        CommandSpec(
            name="doctor",
            phase="cli",
            category="diagnostics",
            option="--doctor",
            description="Check environment, config, input discovery, and output contract.",
            example=".\\neko-core.ps1 --doctor --input C:\\data\\public_test.json",
            guardrail="Diagnostics only; does not call the model or write predictions.",
        ),
        CommandSpec(
            name="capabilities",
            phase="cli",
            category="registry",
            option="--capabilities",
            description="Show runtime, CLI, and development capabilities.",
            example=".\\neko-core.ps1 --capabilities",
            guardrail="Read-only registry surface.",
        ),
        CommandSpec(
            name="agents",
            phase="cli",
            category="registry",
            option="--agents / --agent",
            description="Show harness role boundaries and one-role details.",
            example=".\\neko-core.ps1 --agent task-resolver",
            guardrail="Read-only role registry; does not spawn subagents.",
        ),
        CommandSpec(
            name="tools",
            phase="cli",
            category="registry",
            option="--tools / --tool",
            description="Show tool contracts, permission class, inputs, outputs, and guardrails.",
            example=".\\neko-core.ps1 --tool web-research",
            guardrail="Read-only tool registry; external tools stay quarantined from runtime output.",
        ),
        CommandSpec(
            name="commands",
            phase="cli",
            category="registry",
            option="--commands / --command",
            description="Show this command registry and one-command details.",
            example=".\\neko-core.ps1 --command run",
            guardrail="Read-only command registry; useful before running heavier workflows.",
        ),
        CommandSpec(
            name="workflows",
            phase="cli",
            category="registry",
            option="--list-workflows / --workflow",
            description="List configured workflow profiles or run one by name.",
            example=".\\neko-core.ps1 --workflow quick-dry-run --input C:\\data\\public_test.json --limit 5",
            guardrail="Runtime workflows remain config-defined instead of source-hardcoded.",
        ),
        CommandSpec(
            name="model-inventory",
            phase="development",
            category="provider",
            option="--model-inventory",
            description="Probe provider models and filter Bang C eligible families.",
            example=".\\neko-core.ps1 --model-inventory --run-dir run-model-inventory",
            guardrail="Provider metadata only; does not send contest questions.",
        ),
        CommandSpec(
            name="run",
            phase="runtime",
            category="contest",
            option="--input / --data-dir / --output-dir",
            description=f"Read contest input, solve problems, and write {output_file}.",
            example=".\\neko-core.ps1 --workflow contest-auto --data-dir /data --output-dir /output",
            guardrail="Final path writes only the configured qid,answer prediction CSV.",
        ),
        CommandSpec(
            name="run-session",
            phase="development",
            category="experiment",
            option="--run-dir",
            description="Create a portable run folder with output, traces, report, tasks, and events.",
            example=".\\neko-core.ps1 --workflow quick-dry-run --input C:\\data\\public_test.json --run-dir run-smoke --limit 5",
            guardrail="Development session wrapper; final contest output contract stays unchanged.",
        ),
        CommandSpec(
            name="sessions",
            phase="development",
            category="resume",
            option="--list-runs / --session / --events",
            description="Rediscover local run sessions and render resume-ready state.",
            example=".\\neko-core.ps1 --session run-smoke",
            guardrail="Read-only session inspection; no hidden state required.",
        ),
        CommandSpec(
            name="trace-review",
            phase="development",
            category="verification",
            option="--review-trace / --review-tasks / --compare-traces",
            description="Review trace artifacts, create qid tasks, and compare runs.",
            example=".\\neko-core.ps1 --review-tasks run-smoke\\traces --run-dir run-review-tasks",
            guardrail="Review outputs are evidence; they do not mutate pred.csv.",
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
