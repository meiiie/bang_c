from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "default.json"


@dataclass(frozen=True)
class HarnessConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def schema_version(self) -> str:
        return str(self.raw.get("schema_version", ""))

    @property
    def input_candidates(self) -> tuple[str, ...]:
        return tuple(self.raw["contest"]["input_candidates"])

    @property
    def output_file(self) -> str:
        return str(self.raw["contest"].get("output_file", "pred.csv"))

    @property
    def output_columns(self) -> tuple[str, ...]:
        return tuple(self.raw["contest"].get("output_columns", ("qid", "answer")))

    @property
    def default_model(self) -> str:
        return str(self.raw["runtime"]["default_model"])

    @property
    def base_url(self) -> str:
        return str(self.raw["runtime"]["base_url"])

    @property
    def default_strategy(self) -> str:
        return str(self.raw["runtime"].get("default_strategy", "auto"))

    @property
    def max_retries(self) -> int:
        return int(self.raw["runtime"].get("max_retries", 2))

    @property
    def timeout_seconds(self) -> int:
        return int(self.raw["runtime"].get("timeout_seconds", 90))

    @property
    def thresholds(self) -> dict[str, int]:
        return {
            str(key): int(value)
            for key, value in self.raw["profiling"]["thresholds"].items()
        }

    @property
    def markers(self) -> dict[str, tuple[str, ...]]:
        return {
            str(key): tuple(str(item) for item in value)
            for key, value in self.raw["profiling"]["markers"].items()
        }

    @property
    def rubric(self) -> dict[str, int]:
        return {str(key): int(value) for key, value in self.raw["rubric"].items()}


def load_config(path: str | Path | None = None) -> HarnessConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(raw, config_path)
    return HarnessConfig(raw=raw, path=config_path)


def _validate_config(raw: dict[str, Any], path: Path) -> None:
    required_top = {"schema_version", "contest", "runtime", "profiling", "rubric"}
    missing = required_top - set(raw)
    if missing:
        raise ValueError(f"Config {path} missing top-level keys: {sorted(missing)}")

    if raw["schema_version"] != "bang_c.harness_config.v1":
        raise ValueError(f"Unsupported config schema: {raw['schema_version']}")

    if raw["contest"].get("output_columns") != ["qid", "answer"]:
        raise ValueError("Contest output columns must be exactly ['qid', 'answer']")

    thresholds = raw["profiling"].get("thresholds", {})
    for key in ("many_choice_min", "long_context_chars", "short_question_chars", "focus_tail_chars"):
        if key not in thresholds:
            raise ValueError(f"Config {path} missing profiling threshold: {key}")

    markers = raw["profiling"].get("markers", {})
    for key in ("question", "context", "negative", "calculation"):
        if not markers.get(key):
            raise ValueError(f"Config {path} missing profiling markers: {key}")
