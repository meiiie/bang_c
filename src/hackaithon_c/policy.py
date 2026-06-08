from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .agents import list_agents
from .command_registry import list_commands
from .config import HarnessConfig
from .tool_registry import list_tools


@dataclass(frozen=True)
class PolicyFinding:
    severity: str
    code: str
    message: str
    subject: str


@dataclass(frozen=True)
class PolicyReport:
    verdict: str
    findings: tuple[PolicyFinding, ...]


_DEV_OUTPUT_MARKERS = ("traces/", "run-report.md", "events.jsonl", "review", "task-resolution")


def evaluate_policy(config: HarnessConfig) -> PolicyReport:
    findings: list[PolicyFinding] = []
    agents = list_agents(config)
    tools = list_tools(config)
    commands = list_commands(config)

    _check_unique("agent", (agent.name for agent in agents), findings)
    _check_unique("tool", (tool.name for tool in tools), findings)
    _check_unique("command", (command.name for command in commands), findings)

    for tool in tools:
        if tool.phase == "runtime":
            if tool.status == "external":
                findings.append(
                    PolicyFinding(
                        "fail",
                        "runtime_external_tool",
                        "Runtime tools must not be marked external.",
                        tool.name,
                    )
                )
            if tool.permission.startswith("quarantined"):
                findings.append(
                    PolicyFinding(
                        "fail",
                        "runtime_quarantined_tool",
                        "Quarantined tools must stay out of the runtime phase.",
                        tool.name,
                    )
                )
            for output in tool.outputs:
                if _looks_like_dev_output(output):
                    findings.append(
                        PolicyFinding(
                            "fail",
                            "runtime_dev_output",
                            "Runtime tools must not write development-only artifacts.",
                            f"{tool.name}:{output}",
                        )
                    )
        elif tool.status == "external" and not tool.permission.startswith("quarantined"):
            findings.append(
                PolicyFinding(
                    "fail",
                    "external_tool_not_quarantined",
                    "External development tools must use a quarantined permission class.",
                    tool.name,
                )
            )

    for required_external in ("web-research", "subagent-review"):
        matching = [tool for tool in tools if tool.name == required_external]
        if not matching:
            findings.append(
                PolicyFinding(
                    "fail",
                    "missing_quarantined_tool",
                    "Expected development-only external tool is missing.",
                    required_external,
                )
            )
        elif matching[0].phase != "development" or not matching[0].permission.startswith("quarantined"):
            findings.append(
                PolicyFinding(
                    "fail",
                    "quarantine_boundary_broken",
                    "External research/review tools must stay development-only and quarantined.",
                    required_external,
                )
            )

    run_commands = [command for command in commands if command.name == "run"]
    if not run_commands:
        findings.append(
            PolicyFinding("fail", "missing_runtime_run_command", "Runtime run command is missing.", "run")
        )
    elif run_commands[0].phase != "runtime":
        findings.append(
            PolicyFinding(
                "fail",
                "run_command_not_runtime",
                "The run command must be classified as runtime.",
                "run",
            )
        )

    exporter = [tool for tool in tools if tool.name == "exporter"]
    if not exporter:
        findings.append(
            PolicyFinding("fail", "missing_exporter", "Runtime exporter tool is missing.", "exporter")
        )
    elif "/output/pred.csv" not in exporter[0].outputs:
        findings.append(
            PolicyFinding(
                "fail",
                "exporter_contract_drift",
                "Exporter must write the contest pred.csv artifact.",
                "exporter",
            )
        )

    if any(finding.severity == "fail" for finding in findings):
        verdict = "fail"
    elif any(finding.severity == "warn" for finding in findings):
        verdict = "warn"
    else:
        verdict = "pass"
    return PolicyReport(verdict=verdict, findings=tuple(findings))


def render_policy_report(report: PolicyReport) -> str:
    lines = [
        "Neko Core policy",
        f"Verdict: {report.verdict.upper()}",
    ]
    if not report.findings:
        lines.extend(
            (
                "",
                "Findings:",
                "- PASS runtime/development boundaries are consistent.",
            )
        )
        return "\n".join(lines)

    lines.extend(("", "Findings:"))
    for finding in report.findings:
        lines.append(
            f"- {finding.severity.upper()} {finding.code} [{finding.subject}]: {finding.message}"
        )
    return "\n".join(lines)


def _check_unique(kind: str, names: Iterable[str], findings: list[PolicyFinding]) -> None:
    counts = Counter(str(name) for name in names)
    for name, count in sorted(counts.items()):
        if count > 1:
            findings.append(
                PolicyFinding(
                    "fail",
                    f"duplicate_{kind}",
                    f"{kind.capitalize()} names must be unique.",
                    name,
                )
            )


def _looks_like_dev_output(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _DEV_OUTPUT_MARKERS)
