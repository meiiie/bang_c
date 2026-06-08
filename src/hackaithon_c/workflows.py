from __future__ import annotations

from dataclasses import dataclass

from .config import HarnessConfig


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    description: str
    strategy: str
    verify: bool
    dry_run: bool
    phase: str


def list_workflows(config: HarnessConfig) -> tuple[WorkflowSpec, ...]:
    workflows = []
    for name, raw in sorted(config.workflows.items()):
        workflows.append(
            WorkflowSpec(
                name=name,
                description=str(raw.get("description", "")),
                strategy=str(raw["strategy"]),
                verify=bool(raw.get("verify", False)),
                dry_run=bool(raw.get("dry_run", False)),
                phase=str(raw.get("phase", "development")),
            )
        )
    return tuple(workflows)


def resolve_workflow(config: HarnessConfig, name: str | None) -> WorkflowSpec | None:
    if not name:
        return None
    workflows = {workflow.name: workflow for workflow in list_workflows(config)}
    if name not in workflows:
        available = ", ".join(workflows) or "none"
        raise ValueError(f"Unknown workflow '{name}'. Available workflows: {available}")
    return workflows[name]


def render_workflows(workflows: tuple[WorkflowSpec, ...]) -> str:
    lines = ["Neko Core workflows"]
    for workflow in workflows:
        flags = []
        flags.append(f"strategy={workflow.strategy}")
        if workflow.verify:
            flags.append("verify=true")
        if workflow.dry_run:
            flags.append("dry_run=true")
        lines.append(
            f"[{workflow.phase}] {workflow.name}: {', '.join(flags)} - {workflow.description}"
        )
    return "\n".join(lines)
