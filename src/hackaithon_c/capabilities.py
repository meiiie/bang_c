from __future__ import annotations

from dataclasses import dataclass

from .config import HarnessConfig


@dataclass(frozen=True)
class Capability:
    name: str
    phase: str
    status: str
    detail: str


def collect_capabilities(config: HarnessConfig) -> tuple[Capability, ...]:
    return (
        Capability("contest_io", "runtime", "enabled", "Read /data, write /output/pred.csv"),
        Capability(
            "config_profiler",
            "runtime",
            "enabled",
            "Schema config plus multilingual markers",
        ),
        Capability("model_completion", "runtime", "enabled", config.default_model),
        Capability(
            "repair_invalid_output",
            "runtime",
            "enabled" if config.repair_invalid_output else "disabled",
            "One repair pass before heuristic fallback",
        ),
        Capability(
            "verifier",
            "runtime",
            "enabled",
            "Second answer-only model pass when selected",
        ),
        Capability(
            "tournament",
            "runtime",
            "enabled",
            "Multiple prompt variants with vote synthesis",
        ),
        Capability("doctor", "cli", "enabled", "Environment and contest-contract diagnostics"),
        Capability("model_inventory", "cli", "enabled", "Provider model probe and Bang C filtering"),
        Capability("workflow_registry", "cli", "enabled", "Named runtime and development workflows"),
        Capability(
            "web_research",
            "development",
            "external",
            "Allowed for harness design, excluded from final container",
        ),
        Capability(
            "subagent_review",
            "development",
            "external",
            "Allowed for eval/review work, excluded from final container",
        ),
    )


def render_capabilities(capabilities: tuple[Capability, ...]) -> str:
    lines = ["Neko Core capabilities"]
    for capability in capabilities:
        lines.append(
            f"[{capability.phase}] {capability.name}: {capability.status} - {capability.detail}"
        )
    return "\n".join(lines)
