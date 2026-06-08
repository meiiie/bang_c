from __future__ import annotations

from dataclasses import dataclass

from .config import HarnessConfig


@dataclass(frozen=True)
class ToolSpec:
    name: str
    phase: str
    status: str
    permission: str
    description: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    guardrail: str


def list_tools(config: HarnessConfig) -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(
            name="loader",
            phase="runtime",
            status="enabled",
            permission="filesystem-read",
            description="Finds and parses the contest JSON/CSV input into typed problems.",
            inputs=("/data", ", ".join(config.input_candidates)),
            outputs=("Problem[]",),
            guardrail="Reads only configured input candidates or an explicit local --input path.",
        ),
        ToolSpec(
            name="classifier",
            phase="runtime",
            status="enabled",
            permission="pure-function",
            description="Classifies question shape from config markers and thresholds.",
            inputs=("Problem.question", "Problem.choices", "HarnessConfig"),
            outputs=("ProblemProfile",),
            guardrail="Does not inspect answer keys or public-test-specific labels.",
        ),
        ToolSpec(
            name="solver",
            phase="runtime",
            status="enabled",
            permission="provider-call",
            description="Calls the configured allowed LLM family or dry-run fallback.",
            inputs=("Problem", "ProblemProfile", "NVIDIA_API_KEY", config.default_model),
            outputs=("Prediction", "TraceStep"),
            guardrail="Normalizes to one valid answer letter before export.",
        ),
        ToolSpec(
            name="verifier",
            phase="runtime",
            status="enabled",
            permission="provider-call",
            description="Runs a second answer-only pass when strategy or profile requires it.",
            inputs=("Problem", "candidate answer", "NVIDIA_API_KEY"),
            outputs=("verified Prediction", "TraceStep"),
            guardrail="Can only return a valid option letter for the current problem.",
        ),
        ToolSpec(
            name="exporter",
            phase="runtime",
            status="enabled",
            permission="filesystem-write",
            description="Writes the exact contest artifact.",
            inputs=("Prediction[]",),
            outputs=("/output/pred.csv",),
            guardrail="Writes exactly qid,answer columns for contest output.",
        ),
        ToolSpec(
            name="trace-writer",
            phase="development",
            status="enabled",
            permission="filesystem-write",
            description="Writes trace JSONL, checkpoint, summary, manifest, and run session artifacts.",
            inputs=("Prediction[]", "ValidationSummary", "RunManifest"),
            outputs=("traces/", "predictions.checkpoint.jsonl", "run-report.md", "events.jsonl"),
            guardrail="Development-only; final Docker scoring path does not require traces.",
        ),
        ToolSpec(
            name="trace-reviewer",
            phase="development",
            status="enabled",
            permission="filesystem-read",
            description="Reviews trace artifacts for low confidence, fallbacks, warnings, and contract drift.",
            inputs=("traces/run-summary.json", "traces/predictions.trace.jsonl", "traces/run-manifest.json"),
            outputs=("review findings", "review-tasks.json"),
            guardrail="Read-only review; never mutates pred.csv.",
        ),
        ToolSpec(
            name="task-resolver",
            phase="development",
            status="enabled",
            permission="qid-scoped-rerun",
            description="Reruns selected review-task qids with a chosen workflow and records evidence.",
            inputs=("review-tasks.json", "input dataset", "baseline traces"),
            outputs=("task-resolution.json", "task-resolution-report.md", "comparison.txt"),
            guardrail="Scopes reruns by qid so unrelated answers do not pollute review evidence.",
        ),
        ToolSpec(
            name="model-inventory",
            phase="development",
            status="enabled",
            permission="provider-read",
            description="Lists provider models and filters them by Bang C allowed families.",
            inputs=("NVIDIA_API_KEY", "configs/default.json"),
            outputs=("model-inventory.txt",),
            guardrail="Does not send contest questions to the model inventory endpoint.",
        ),
        ToolSpec(
            name="web-research",
            phase="development",
            status="external",
            permission="quarantined-read",
            description="Researches public docs or model behavior outside the final runtime path.",
            inputs=("public URLs", "human-reviewed notes"),
            outputs=("development notes", "config or test proposals"),
            guardrail="Untrusted web content cannot write pred.csv or execute privileged actions.",
        ),
        ToolSpec(
            name="subagent-review",
            phase="development",
            status="external",
            permission="quarantined-review",
            description="Uses separate review contexts for eval, hypothesis checks, and trace critique.",
            inputs=("run artifacts", "rubric", "review tasks"),
            outputs=("review report", "candidate improvements"),
            guardrail="Reviewer output must be converted into tests or config changes before runtime use.",
        ),
    )


def resolve_tool(config: HarnessConfig, name: str) -> ToolSpec:
    tools = {tool.name: tool for tool in list_tools(config)}
    if name not in tools:
        available = ", ".join(tools) or "none"
        raise ValueError(f"Unknown tool '{name}'. Available tools: {available}")
    return tools[name]


def render_tools(tools: tuple[ToolSpec, ...]) -> str:
    lines = ["Neko Core tools"]
    for tool in tools:
        lines.append(
            f"[{tool.phase}] {tool.name}: {tool.status}, {tool.permission} - {tool.description}"
        )
    return "\n".join(lines)


def render_tool_detail(tool: ToolSpec) -> str:
    lines = [
        "Neko Core Tool",
        f"Name: {tool.name}",
        f"Phase: {tool.phase}",
        f"Status: {tool.status}",
        f"Permission: {tool.permission}",
        f"Description: {tool.description}",
        "",
        "Inputs:",
    ]
    lines.extend(f"- {item}" for item in tool.inputs)
    lines.extend(["", "Outputs:"])
    lines.extend(f"- {item}" for item in tool.outputs)
    lines.extend(["", "Guardrail:", f"- {tool.guardrail}"])
    return "\n".join(lines)
