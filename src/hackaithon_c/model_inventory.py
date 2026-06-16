from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from .config import HarnessConfig


@dataclass(frozen=True)
class ModelInventoryItem:
    model_id: str
    category: str
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ModelInventoryReport:
    status: str
    base_url: str
    default_model: str
    effective_model: str
    total_models: int
    selected_model_allowed: bool
    selected_model_reason: str
    items: tuple[ModelInventoryItem, ...]
    error: str | None = None


def collect_model_inventory(
    config: HarnessConfig,
    *,
    payload: Any | None = None,
) -> ModelInventoryReport:
    base_url = os.environ.get("NVIDIA_BASE_URL", config.base_url).rstrip("/")
    effective_model = os.environ.get("HACKC_LLM_MODEL", config.api_model).strip()
    if not effective_model:
        effective_model = config.api_model
    policy = policy_from_config(config)

    if payload is None:
        api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if not api_key:
            return _report(
                status="warn",
                base_url=base_url,
                default_model=config.api_model,
                effective_model=effective_model,
                model_ids=(),
                policy=policy,
                error="NVIDIA_API_KEY missing; cannot query /models.",
            )
        try:
            payload = _fetch_models(base_url, api_key, timeout_seconds=config.timeout_seconds)
        except Exception as error:  # noqa: BLE001 - diagnostic boundary
            return _report(
                status="fail",
                base_url=base_url,
                default_model=config.api_model,
                effective_model=effective_model,
                model_ids=(),
                policy=policy,
                error=f"Model inventory request failed: {error}",
            )

    return _report(
        status="ok",
        base_url=base_url,
        default_model=config.api_model,
        effective_model=effective_model,
        model_ids=tuple(_extract_model_ids(payload)),
        policy=policy,
        error=None,
    )


def render_model_inventory(report: ModelInventoryReport) -> str:
    lines = [
        "Neko Core model inventory",
        f"[{report.status.upper()}] provider: {report.base_url}/models",
        f"Default model: {report.default_model}",
        f"Effective model: {report.effective_model}",
        f"Effective model allowed: {report.selected_model_allowed} ({report.selected_model_reason})",
        f"Models seen: {report.total_models}",
    ]
    if report.error:
        lines.append(f"Note: {report.error}")

    allowed_llm = [item for item in report.items if item.allowed and item.category == "llm"]
    allowed_tools = [
        item
        for item in report.items
        if item.allowed and item.category == "embedding_rerank"
    ]

    lines.append("")
    lines.append("Allowed LLM models:")
    if allowed_llm:
        for item in allowed_llm:
            lines.append(f"- {item.model_id}: {item.reason}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Allowed embedding/rerank models:")
    if allowed_tools:
        for item in allowed_tools:
            lines.append(f"- {item.model_id}: {item.reason}")
    else:
        lines.append("- none")
    return "\n".join(lines)


@dataclass(frozen=True)
class FamilyRule:
    """One allowed model family expressed as DATA: substring `aliases` + an optional `max_params_b`
    size cap. ``max_params_b=None`` = no size limit for this family. Add a family by appending a rule
    to ``runtime.model_policy`` in the config — no code change."""
    aliases: tuple[str, ...]
    max_params_b: float | None = None


@dataclass(frozen=True)
class ModelPolicy:
    """The Bang-C model allowlist, config-driven (no hardcoded per-model branches).
    ``count_active_for_moe`` decides whether an MoE id's size is read from its active (``aNb``) or
    total (``Nb``) token — flip it if the organisers count active params."""
    llm: tuple[FamilyRule, ...]
    embedding: tuple[FamilyRule, ...]
    count_active_for_moe: bool = False


# Backward-compatible default = the historical rules (Gemma-4 any size; Qwen3.5 <= 9B; BGE-M3 / Qwen-Rerank).
# The ship config overrides this via runtime.model_policy; change THAT to pivot (e.g. a <=5B cap on a
# broader family set). Kept here so callers/tests without a config still get the legacy semantics.
DEFAULT_POLICY = ModelPolicy(
    llm=(
        FamilyRule(aliases=("gemma-4", "gemma4"), max_params_b=None),
        FamilyRule(aliases=("qwen3.5", "qwen-3.5"), max_params_b=9.0),
    ),
    embedding=(
        FamilyRule(aliases=("bge-m3",)),
        FamilyRule(aliases=("qwen-rerank", "qwen_rerank")),
    ),
)


def _rules_from_config(items: Any) -> tuple[FamilyRule, ...]:
    out: list[FamilyRule] = []
    for item in items or ():
        aliases = tuple(str(a).lower() for a in item.get("aliases", ()) if str(a).strip())
        if not aliases:
            continue
        cap = item.get("max_params_b")
        out.append(FamilyRule(aliases=aliases, max_params_b=float(cap) if cap is not None else None))
    return tuple(out)


def policy_from_config(config: HarnessConfig) -> ModelPolicy:
    """Build the ModelPolicy from ``runtime.model_policy`` (config-first); fall back to DEFAULT_POLICY."""
    raw = getattr(config, "model_policy", None)
    if not isinstance(raw, dict):
        return DEFAULT_POLICY
    return ModelPolicy(
        llm=_rules_from_config(raw.get("llm_families")) or DEFAULT_POLICY.llm,
        embedding=_rules_from_config(raw.get("embedding_families")) or DEFAULT_POLICY.embedding,
        count_active_for_moe=bool(raw.get("count_active_for_moe", False)),
    )


def _params_b(normalized: str, *, active: bool) -> float | None:
    """Parameter count (in B) parsed from a model id. For MoE, `active` reads the ``aNb`` token;
    otherwise the LARGEST ``Nb`` token (the total). Returns None when no size is present in the id."""
    if active:
        m = re.search(r"a(\d+(?:\.\d+)?)b(?![a-z0-9])", normalized)
        if m:
            return float(m.group(1))
    sizes = [float(x) for x in re.findall(r"(?<![a-z0-9])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", normalized)]
    return max(sizes) if sizes else None


def _match_family(normalized: str, rules: tuple[FamilyRule, ...]) -> FamilyRule | None:
    for rule in rules:
        if "*" in rule.aliases or any(alias in normalized for alias in rule.aliases):
            return rule
    return None


def classify_model(model_id: str, *, policy: ModelPolicy = DEFAULT_POLICY) -> ModelInventoryItem:
    """Classify a model id against the (config-driven) policy: embedding/rerank family, an allowed
    LLM family within its size cap, or not allowed. Generic — no per-model hardcoding."""
    normalized = model_id.lower()
    if _match_family(normalized, policy.embedding):
        return ModelInventoryItem(model_id, "embedding_rerank", True, "embedding/rerank family")
    rule = _match_family(normalized, policy.llm)
    if rule is None:
        return ModelInventoryItem(model_id, "other", False, "not allowed by Bang C rules")
    if rule.max_params_b is None:
        return ModelInventoryItem(model_id, "llm", True, "allowed family (no size cap)")
    size = _params_b(normalized, active=policy.count_active_for_moe)
    if size is None:
        return ModelInventoryItem(model_id, "llm", False, f"size unknown (cap {rule.max_params_b:g}B)")
    if size <= rule.max_params_b:
        return ModelInventoryItem(model_id, "llm", True, f"{size:g}B <= {rule.max_params_b:g}B")
    return ModelInventoryItem(model_id, "llm", False, f"{size:g}B > {rule.max_params_b:g}B cap")


def _report(
    *,
    status: str,
    base_url: str,
    default_model: str,
    effective_model: str,
    model_ids: tuple[str, ...],
    policy: ModelPolicy,
    error: str | None,
) -> ModelInventoryReport:
    items = tuple(
        classify_model(model_id, policy=policy)
        for model_id in sorted(set(model_ids))
    )
    selected = classify_model(effective_model, policy=policy)
    selected_seen = effective_model in {item.model_id for item in items}
    selected_reason = selected.reason
    if items and not selected_seen:
        selected_reason = f"{selected_reason}; not present in inventory"
    return ModelInventoryReport(
        status=status,
        base_url=base_url,
        default_model=default_model,
        effective_model=effective_model,
        total_models=len(items),
        selected_model_allowed=selected.allowed and (not items or selected_seen),
        selected_model_reason=selected_reason,
        items=items,
        error=error,
    )


def _fetch_models(base_url: str, api_key: str, *, timeout_seconds: int) -> Any:
    import requests

    response = requests.get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _extract_model_ids(payload: Any) -> list[str]:
    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return []

    model_ids: list[str] = []
    for record in records:
        if isinstance(record, str):
            model_ids.append(record)
        elif isinstance(record, dict) and record.get("id"):
            model_ids.append(str(record["id"]))
    return model_ids
