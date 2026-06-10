from __future__ import annotations

from dataclasses import dataclass

from .config import HarnessConfig


@dataclass(frozen=True)
class AgentSpec:
    name: str
    phase: str
    mode: str
    description: str
    tools: tuple[str, ...]
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    handoff: str


def list_agents(config: HarnessConfig) -> tuple[AgentSpec, ...]:
    return (
        AgentSpec(
            name="runner",
            phase="runtime",
            mode="orchestrator",
            description="Loads input, routes qids through the configured workflow, and writes pred.csv.",
            tools=("loader", "classifier", "solver", "exporter"),
            reads=("/data", config.path.name),
            writes=("/output/pred.csv",),
            handoff="Produces the contest artifact and optional run session artifacts.",
        ),
        AgentSpec(
            name="classifier",
            phase="runtime",
            mode="deterministic",
            description="Profiles question shape without using public-test answer assumptions.",
            tools=("config markers", "text heuristics"),
            reads=("Problem.question", "Problem.choices", "configs/default.json"),
            writes=("ProblemProfile",),
            handoff="Selects prompt variant and whether verification or tournament is appropriate.",
        ),
        AgentSpec(
            name="solver",
            phase="runtime",
            mode="model-routed",
            description="Calls the configured local/API LLM family or deterministic dry-run fallback.",
            tools=("local llama.cpp GGUF", "NVIDIA NIM OpenAI-compatible chat", "normalizer", "heuristic fallback"),
            reads=("Problem", "ProblemProfile", "HarnessConfig"),
            writes=("Prediction", "TraceStep"),
            handoff="Returns one normalized choice letter plus structured trace steps.",
        ),
        AgentSpec(
            name="verifier",
            phase="runtime",
            mode="model-routed",
            description="Runs answer-only second pass when selected by workflow or CLI flags.",
            tools=("local llama.cpp GGUF", "NVIDIA NIM OpenAI-compatible chat", "normalizer"),
            reads=("Problem", "solver answer"),
            writes=("verified Prediction", "TraceStep"),
            handoff="Can replace the solver answer when the verifier returns a valid choice.",
        ),
        AgentSpec(
            name="trace-reviewer",
            phase="development",
            mode="read-only",
            description="Reviews run-summary, trace JSONL, and manifest for contract or confidence issues.",
            tools=("trace reader", "manifest checks", "review task builder"),
            reads=("traces/run-summary.json", "traces/predictions.trace.jsonl", "traces/run-manifest.json"),
            writes=("review-tasks.md", "review-tasks.json"),
            handoff="Creates deterministic follow-up tasks without mutating pred.csv.",
        ),
        AgentSpec(
            name="task-resolver",
            phase="development",
            mode="qid-scoped runner",
            description="Reruns review-task qids with a selected workflow and records before/after evidence.",
            tools=("scripts/resolve-tasks.ps1", "--qid", "--compare-qid"),
            reads=("review-tasks.json", "input dataset", "baseline traces"),
            writes=("task-resolution-report.md", "task-resolution.json", "comparison.txt"),
            handoff="Hands resolved qid evidence back to the human or next reviewer.",
        ),
        AgentSpec(
            name="session-inspector",
            phase="development",
            mode="read-only",
            description="Rediscovers local run sessions and renders resume-ready status.",
            tools=("--list-runs", "--session", "--events"),
            reads=("run-report.md", "run-manifest.json", "events.jsonl"),
            writes=(),
            handoff="Shows the next review or resolve command for a run folder.",
        ),
        AgentSpec(
            name="model-inventory",
            phase="development",
            mode="provider probe",
            description="Lists API provider models and filters them against Bang C model-family rules.",
            tools=("NVIDIA /models", "model classifier"),
            reads=("NVIDIA_API_KEY", "configs/default.json"),
            writes=("model-inventory.txt",),
            handoff="Identifies eligible LLM and embedding/rerank candidates before experiments.",
        ),
    )


def resolve_agent(config: HarnessConfig, name: str) -> AgentSpec:
    agents = {agent.name: agent for agent in list_agents(config)}
    if name not in agents:
        available = ", ".join(agents) or "none"
        raise ValueError(f"Unknown agent '{name}'. Available agents: {available}")
    return agents[name]


def render_agents(agents: tuple[AgentSpec, ...]) -> str:
    lines = ["Neko Core agents"]
    for agent in agents:
        lines.append(f"[{agent.phase}] {agent.name}: {agent.mode} - {agent.description}")
    return "\n".join(lines)


def render_agent_detail(agent: AgentSpec) -> str:
    lines = [
        "Neko Core Agent",
        f"Name: {agent.name}",
        f"Phase: {agent.phase}",
        f"Mode: {agent.mode}",
        f"Description: {agent.description}",
        "",
        "Tools:",
    ]
    lines.extend(f"- {tool}" for tool in agent.tools)
    lines.extend(["", "Reads:"])
    lines.extend(f"- {item}" for item in agent.reads)
    lines.extend(["", "Writes:"])
    if agent.writes:
        lines.extend(f"- {item}" for item in agent.writes)
    else:
        lines.append("- none")
    lines.extend(["", "Handoff:", f"- {agent.handoff}"])
    return "\n".join(lines)
