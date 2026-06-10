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

    if payload is None:
        api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if not api_key:
            return _report(
                status="warn",
                base_url=base_url,
                default_model=config.api_model,
                effective_model=effective_model,
                model_ids=(),
                allowed_llm_families=config.allowed_model_families,
                allowed_embedding_families=config.allowed_embedding_families,
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
                allowed_llm_families=config.allowed_model_families,
                allowed_embedding_families=config.allowed_embedding_families,
                error=f"Model inventory request failed: {error}",
            )

    return _report(
        status="ok",
        base_url=base_url,
        default_model=config.api_model,
        effective_model=effective_model,
        model_ids=tuple(_extract_model_ids(payload)),
        allowed_llm_families=config.allowed_model_families,
        allowed_embedding_families=config.allowed_embedding_families,
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


def classify_model(
    model_id: str,
    *,
    allowed_llm_families: tuple[str, ...] = ("gemma-4", "qwen3.5"),
    allowed_embedding_families: tuple[str, ...] = ("bge-m3", "qwen-rerank"),
) -> ModelInventoryItem:
    normalized = model_id.lower()
    llm_families = tuple(item.lower() for item in allowed_llm_families)
    embedding_families = tuple(item.lower() for item in allowed_embedding_families)

    if "gemma-4" in llm_families and "gemma-4" in normalized:
        return ModelInventoryItem(model_id, "llm", True, "gemma-4 series")

    if "qwen3.5" in llm_families and (
        "qwen3.5" in normalized or "qwen-3.5" in normalized
    ):
        size_b = _extract_qwen3_5_billion_params(normalized)
        if size_b is not None and size_b <= 9:
            return ModelInventoryItem(model_id, "llm", True, "qwen3.5 <= 9B")
        if size_b is None:
            return ModelInventoryItem(model_id, "llm", False, "qwen3.5 size unknown")
        return ModelInventoryItem(model_id, "llm", False, "qwen3.5 above 9B")

    if "bge-m3" in embedding_families and "bge-m3" in normalized:
        return ModelInventoryItem(model_id, "embedding_rerank", True, "BGE-M3")

    if "qwen-rerank" in embedding_families and (
        "qwen-rerank" in normalized or "qwen_rerank" in normalized
    ):
        return ModelInventoryItem(model_id, "embedding_rerank", True, "Qwen-Rerank")

    return ModelInventoryItem(model_id, "other", False, "not allowed by Bang C rules")


def _report(
    *,
    status: str,
    base_url: str,
    default_model: str,
    effective_model: str,
    model_ids: tuple[str, ...],
    allowed_llm_families: tuple[str, ...],
    allowed_embedding_families: tuple[str, ...],
    error: str | None,
) -> ModelInventoryReport:
    items = tuple(
        classify_model(
            model_id,
            allowed_llm_families=allowed_llm_families,
            allowed_embedding_families=allowed_embedding_families,
        )
        for model_id in sorted(set(model_ids))
    )
    selected = classify_model(
        effective_model,
        allowed_llm_families=allowed_llm_families,
        allowed_embedding_families=allowed_embedding_families,
    )
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


def _extract_billion_params(value: str) -> float | None:
    match = re.search(r"(?<![a-z0-9])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", value)
    if not match:
        match = re.search(r"[-_/](\d+(?:\.\d+)?)b(?:[-_/]|$)", value)
    if not match:
        return None
    return float(match.group(1))


def _extract_qwen3_5_billion_params(value: str) -> float | None:
    marker_index = value.find("qwen3.5")
    marker_length = len("qwen3.5")
    if marker_index < 0:
        marker_index = value.find("qwen-3.5")
        marker_length = len("qwen-3.5")
    if marker_index < 0:
        return _extract_billion_params(value)
    return _extract_billion_params(value[marker_index + marker_length :])
