from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_NAME = "default.json"
LOCAL_CONFIG_DIR = ".neko-core"
LOCAL_CONFIG_NAME = "config.json"


@dataclass(frozen=True)
class HarnessConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def schema_version(self) -> str:
        return str(self.raw.get("schema_version", ""))

    @property
    def brand_name(self) -> str:
        return str(self.raw.get("brand", {}).get("name", "Neko Core"))

    @property
    def brand_slug(self) -> str:
        return str(self.raw.get("brand", {}).get("slug", "neko-core"))

    @property
    def ascii_logo(self) -> tuple[str, ...]:
        return tuple(str(line) for line in self.raw.get("brand", {}).get("ascii_logo", ()))

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
    def allowed_model_families(self) -> tuple[str, ...]:
        return tuple(
            str(item)
            for item in self.raw["runtime"].get("allowed_model_families", ())
        )

    @property
    def allowed_embedding_families(self) -> tuple[str, ...]:
        return tuple(
            str(item)
            for item in self.raw["runtime"].get(
                "allowed_embedding_families",
                ("bge-m3", "qwen-rerank"),
            )
        )

    @property
    def default_strategy(self) -> str:
        return str(self.raw["runtime"].get("default_strategy", "auto"))

    @property
    def max_retries(self) -> int:
        return int(self.raw["runtime"].get("max_retries", 6))

    @property
    def retry_base_delay_seconds(self) -> float:
        return float(self.raw["runtime"].get("retry_base_delay_seconds", 1.5))

    @property
    def retry_max_delay_seconds(self) -> float:
        return float(self.raw["runtime"].get("retry_max_delay_seconds", 30.0))

    @property
    def problem_max_retries(self) -> int:
        return int(self.raw["runtime"].get("problem_max_retries", 2))

    @property
    def problem_retry_base_delay_seconds(self) -> float:
        return float(self.raw["runtime"].get("problem_retry_base_delay_seconds", 5.0))

    @property
    def problem_retry_max_delay_seconds(self) -> float:
        return float(self.raw["runtime"].get("problem_retry_max_delay_seconds", 60.0))

    @property
    def timeout_seconds(self) -> int:
        return int(self.raw["runtime"].get("timeout_seconds", 90))

    @property
    def repair_invalid_output(self) -> bool:
        return bool(self.raw["runtime"].get("repair_invalid_output", True))

    @property
    def workflows(self) -> dict[str, dict[str, Any]]:
        return {
            str(name): dict(value)
            for name, value in self.raw.get("workflows", {}).items()
        }

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
    config_path = Path(path) if path else _default_config_path()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_config(raw, config_path)
    return HarnessConfig(raw=raw, path=config_path)


def _default_config_path() -> Path:
    candidates = (
        Path.cwd() / LOCAL_CONFIG_DIR / LOCAL_CONFIG_NAME,
        Path.cwd() / "configs" / DEFAULT_CONFIG_NAME,
        Path(__file__).resolve().parents[2] / "configs" / DEFAULT_CONFIG_NAME,
        Path(__file__).resolve().parent / "resources" / DEFAULT_CONFIG_NAME,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Default config not found. Run from the repository root or pass --config."
    )


def _validate_config(raw: dict[str, Any], path: Path) -> None:
    required_top = {"schema_version", "contest", "runtime", "profiling", "rubric"}
    missing = required_top - set(raw)
    if missing:
        raise ValueError(f"Config {path} missing top-level keys: {sorted(missing)}")

    if raw["schema_version"] != "bang_c.harness_config.v1":
        raise ValueError(f"Unsupported config schema: {raw['schema_version']}")

    if raw["contest"].get("output_columns") != ["qid", "answer"]:
        raise ValueError("Contest output columns must be exactly ['qid', 'answer']")

    if not raw["runtime"].get("allowed_model_families"):
        raise ValueError(f"Config {path} missing runtime.allowed_model_families")
    if int(raw["runtime"].get("max_retries", 0)) < 0:
        raise ValueError(f"Config {path} runtime.max_retries must be >= 0")
    if float(raw["runtime"].get("retry_base_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.retry_base_delay_seconds must be >= 0"
        )
    if float(raw["runtime"].get("retry_max_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.retry_max_delay_seconds must be >= 0"
        )
    if int(raw["runtime"].get("problem_max_retries", 0)) < 0:
        raise ValueError(f"Config {path} runtime.problem_max_retries must be >= 0")
    if float(raw["runtime"].get("problem_retry_base_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.problem_retry_base_delay_seconds must be >= 0"
        )
    if float(raw["runtime"].get("problem_retry_max_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.problem_retry_max_delay_seconds must be >= 0"
        )

    thresholds = raw["profiling"].get("thresholds", {})
    for key in ("many_choice_min", "long_context_chars", "short_question_chars", "focus_tail_chars"):
        if key not in thresholds:
            raise ValueError(f"Config {path} missing profiling threshold: {key}")

    markers = raw["profiling"].get("markers", {})
    for key in ("question", "context", "negative", "calculation"):
        if not markers.get(key):
            raise ValueError(f"Config {path} missing profiling markers: {key}")

    valid_strategies = {"auto", "direct", "verify", "tournament"}
    for name, workflow in raw.get("workflows", {}).items():
        if workflow.get("strategy") not in valid_strategies:
            raise ValueError(f"Config {path} workflow {name} has invalid strategy")
        if workflow.get("phase") not in {"runtime", "development"}:
            raise ValueError(f"Config {path} workflow {name} has invalid phase")
