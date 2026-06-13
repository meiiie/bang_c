from __future__ import annotations

import json
import os
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
    profile: str | None = None

    @property
    def runtime(self) -> dict[str, Any]:
        return _effective_runtime(self.raw, self.profile)

    @property
    def active_profile(self) -> str | None:
        return self.runtime.get("active_profile")

    @property
    def runtime_profiles(self) -> dict[str, dict[str, Any]]:
        profiles = self.raw.get("runtime", {}).get("profiles", {})
        if not isinstance(profiles, dict):
            return {}
        return {str(name): dict(value) for name, value in profiles.items()}

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
    def provider(self) -> str:
        return str(self.runtime.get("provider", "local_llamacpp"))

    @property
    def default_model(self) -> str:
        return str(self.runtime["default_model"])

    @property
    def api_model(self) -> str:
        return str(self.runtime.get("api_model", self.default_model))

    @property
    def base_url(self) -> str:
        return str(self.runtime["base_url"])

    @property
    def local_model_path(self) -> str:
        return str(self.runtime.get("local_model_path", "/models/model.gguf"))

    @property
    def local_model_repo(self) -> str:
        return str(self.runtime.get("local_model_repo", ""))

    @property
    def local_model_file(self) -> str:
        return str(self.runtime.get("local_model_file", ""))

    @property
    def local_n_ctx(self) -> int:
        return int(self.runtime.get("local_n_ctx", 8192))

    @property
    def local_n_gpu_layers(self) -> int:
        return int(self.runtime.get("local_n_gpu_layers", -1))

    @property
    def local_n_threads(self) -> int:
        return int(self.runtime.get("local_n_threads", 0))

    @property
    def local_chat_format(self) -> str:
        return str(self.runtime.get("local_chat_format", ""))

    @property
    def allowed_model_families(self) -> tuple[str, ...]:
        return tuple(
            str(item)
            for item in self.runtime.get("allowed_model_families", ())
        )

    @property
    def allowed_embedding_families(self) -> tuple[str, ...]:
        return tuple(
            str(item)
            for item in self.runtime.get(
                "allowed_embedding_families",
                ("bge-m3", "qwen-rerank"),
            )
        )

    @property
    def default_strategy(self) -> str:
        return str(self.runtime.get("default_strategy", "auto"))

    @property
    def self_consistency_samples(self) -> int:
        # k=1 (single deterministic CoT) is the validated contest default: on the real
        # Gemma-4-26B at temperature 0 the samples are identical, so k>1 only adds cost.
        # Keep k=1 unless a future measured workflow beats the current default.
        # The multi-sample voting mechanism is still exercised by tests with explicit k>=2.
        return max(1, int(self.runtime.get("self_consistency_samples", 1)))

    @property
    def reasoning_max_tokens(self) -> int:
        # 2048 validated on the real Gemma-4-26B (A40, 2026-06-10): 512 truncated the
        # chain-of-thought before the "ANSWER:" line, causing ~30% invalid-output
        # fallbacks and wrong answers on calculation/reading items.
        return int(self.runtime.get("reasoning_max_tokens", 2048))

    @property
    def self_consistency_challenge_threshold(self) -> float:
        return float(self.runtime.get("self_consistency_challenge_threshold", 0.75))

    @property
    def challenger_samples(self) -> int:
        return max(1, int(self.runtime.get("challenger_samples", 3)))

    @property
    def reasoning_temperature(self) -> float:
        # Sampling temperature for DIVERSIFIED reasoning samples only (tiered strategy).
        # The anchor sample and the k=1 contest path always run deterministically.
        # 0.8 per Gemma guidance: Gemma-4's tuned operating point is T=1.0/top_p=0.95/
        # top_k=64 and quality degrades at low T; voting literature favors T 0.8-1.0.
        return float(self.runtime.get("reasoning_temperature", 0.8))

    @property
    def reasoning_top_p(self) -> float:
        return float(self.runtime.get("reasoning_top_p", 0.95))

    @property
    def reasoning_top_k(self) -> int:
        return int(self.runtime.get("reasoning_top_k", 64))

    @property
    def reasoning_few_shot_path(self) -> str:
        # Path to a JSON exemplar file for few-shot prompting (empty = zero-shot).
        # Evidence (ViGEText): 0->5-shot Vietnamese exemplars with explicit
        # answer-letter format = +15.4pp average on Vietnamese exam MCQ.
        # Default OFF until A/B-measured on the real model.
        return str(self.runtime.get("reasoning_few_shot_path", "")).strip()

    @property
    def tir_samples(self) -> int:
        # Tool-integrated reasoning: how many independent code+exec+answer passes to
        # vote over (self-consistency on the SETUP, not just the arithmetic). 1 = single
        # pass. Only fires on quantitative questions via the router.
        return max(1, int(self.runtime.get("tir_samples", 1)))

    @property
    def tir_exec_timeout_seconds(self) -> float:
        # Hard wall-clock cap on each model-written program (kills runaway loops).
        return float(self.runtime.get("tir_exec_timeout_seconds", 5.0))

    @property
    def tir_code_max_tokens(self) -> int:
        # Generation budget for the code-writing round (programs are short).
        return int(self.runtime.get("tir_code_max_tokens", 1024))

    @property
    def rag_corpus_path(self) -> str:
        # Path to a JSONL retrieval corpus ({id, title, text} rows) for the targeted
        # legal/admin RAG mode. Empty = RAG OFF (the router never fires it). Built
        # dev-side by scripts/build_rag_corpus.py; packaged into the image only if
        # measurement promotes the lever.
        return str(self.runtime.get("rag_corpus_path", "")).strip()

    @property
    def rag_top_k(self) -> int:
        # How many retrieved excerpts to show the model per question.
        return max(1, int(self.runtime.get("rag_top_k", 4)))

    @property
    def enable_safety_refusal(self) -> bool:
        # Append the safety-refusal clause to the reasoning system prompt: harmful-
        # solicitation items ("how to violate/falsify/sabotage/evade...") whose option
        # list contains a refusal answer have that refusal as the gold. Off by default
        # (the contest path stays untouched until the lever is externally validated).
        # Generalizes by SEMANTICS, not keywords: the model judges harm, so it carries
        # to the multilingual private test. Default OFF keeps the validated contest path.
        return bool(self.runtime.get("enable_safety_refusal", False))

    @property
    def tiered_tier1_samples(self) -> int:
        # Tier 1 = anchor + rotated-choice samples; unanimous agreement stops early.
        return max(1, int(self.runtime.get("tiered_tier1_samples", 2)))

    @property
    def tiered_total_samples(self) -> int:
        # Escalation budget when tier 1 disagrees (total samples incl. tier 1).
        return max(
            self.tiered_tier1_samples,
            int(self.runtime.get("tiered_total_samples", 5)),
        )

    @property
    def local_flash_attn(self) -> bool:
        # Pure-speed flag (no accuracy semantics): enable llama.cpp flash attention.
        # Default off until validated on the contest GPU; flip via config or
        # HACKC_LLAMACPP_FLASH_ATTN=1.
        return bool(self.runtime.get("local_flash_attn", False))

    @property
    def local_n_batch(self) -> int:
        return int(self.runtime.get("local_n_batch", 0))

    @property
    def local_server_url(self) -> str:
        return str(
            self.runtime.get("local_server_url", "http://127.0.0.1:8080/v1")
        ).strip()

    @property
    def challenger_provider(self) -> str:
        return str(self.runtime.get("challenger_provider", "")).strip()

    @property
    def challenger_model_path(self) -> str:
        return str(self.runtime.get("challenger_model_path", "")).strip()

    @property
    def challenger_model_id(self) -> str:
        return str(self.runtime.get("challenger_model_id", "")).strip()

    @property
    def max_retries(self) -> int:
        return int(self.runtime.get("max_retries", 6))

    @property
    def retry_base_delay_seconds(self) -> float:
        return float(self.runtime.get("retry_base_delay_seconds", 1.5))

    @property
    def retry_max_delay_seconds(self) -> float:
        return float(self.runtime.get("retry_max_delay_seconds", 30.0))

    @property
    def problem_max_retries(self) -> int:
        return int(self.runtime.get("problem_max_retries", 2))

    @property
    def problem_retry_base_delay_seconds(self) -> float:
        return float(self.runtime.get("problem_retry_base_delay_seconds", 5.0))

    @property
    def problem_retry_max_delay_seconds(self) -> float:
        return float(self.runtime.get("problem_retry_max_delay_seconds", 60.0))

    @property
    def timeout_seconds(self) -> int:
        return int(self.runtime.get("timeout_seconds", 90))

    @property
    def repair_invalid_output(self) -> bool:
        return bool(self.runtime.get("repair_invalid_output", True))

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


def load_config(path: str | Path | None = None, *, profile: str | None = None) -> HarnessConfig:
    config_path = Path(path) if path else _default_config_path()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    active_profile = _selected_profile(raw, profile)
    _validate_config(raw, config_path, active_profile)
    return HarnessConfig(raw=raw, path=config_path, profile=active_profile)


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


def _validate_config(raw: dict[str, Any], path: Path, active_profile: str | None) -> None:
    required_top = {"schema_version", "contest", "runtime", "profiling", "rubric"}
    missing = required_top - set(raw)
    if missing:
        raise ValueError(f"Config {path} missing top-level keys: {sorted(missing)}")

    if raw["schema_version"] != "bang_c.harness_config.v1":
        raise ValueError(f"Unsupported config schema: {raw['schema_version']}")

    if raw["contest"].get("output_columns") != ["qid", "answer"]:
        raise ValueError("Contest output columns must be exactly ['qid', 'answer']")

    runtime = _effective_runtime(raw, active_profile)
    profiles = raw["runtime"].get("profiles", {})
    if profiles is not None and not isinstance(profiles, dict):
        raise ValueError(f"Config {path} runtime.profiles must be an object")
    if runtime.get("provider", "local_llamacpp") not in {"local_llamacpp", "nvidia", "local_server"}:
        raise ValueError(
            f"Config {path} runtime.provider must be local_llamacpp, nvidia, or local_server"
        )
    if not runtime.get("allowed_model_families"):
        raise ValueError(f"Config {path} missing runtime.allowed_model_families")
    if not runtime.get("default_model"):
        raise ValueError(f"Config {path} missing runtime.default_model")
    if runtime.get("provider", "local_llamacpp") == "local_llamacpp" and not runtime.get("local_model_path"):
        raise ValueError(f"Config {path} missing runtime.local_model_path")
    if int(runtime.get("max_retries", 0)) < 0:
        raise ValueError(f"Config {path} runtime.max_retries must be >= 0")
    if float(runtime.get("retry_base_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.retry_base_delay_seconds must be >= 0"
        )
    if float(runtime.get("retry_max_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.retry_max_delay_seconds must be >= 0"
        )
    if int(runtime.get("problem_max_retries", 0)) < 0:
        raise ValueError(f"Config {path} runtime.problem_max_retries must be >= 0")
    if float(runtime.get("problem_retry_base_delay_seconds", 0)) < 0:
        raise ValueError(
            f"Config {path} runtime.problem_retry_base_delay_seconds must be >= 0"
        )
    if float(runtime.get("problem_retry_max_delay_seconds", 0)) < 0:
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

    valid_strategies = {
        "auto",
        "direct",
        "verify",
        "tournament",
        "self_consistency",
        "tiered",
        "tir",
        "reading",
        "rag",
        "router",
    }
    for name, workflow in raw.get("workflows", {}).items():
        if workflow.get("strategy") not in valid_strategies:
            raise ValueError(f"Config {path} workflow {name} has invalid strategy")
        if workflow.get("phase") not in {"runtime", "development"}:
            raise ValueError(f"Config {path} workflow {name} has invalid phase")


def _selected_profile(raw: dict[str, Any], requested_profile: str | None) -> str | None:
    profile = (
        requested_profile
        or os.environ.get("HACKC_PROFILE", "").strip()
        or str(raw.get("runtime", {}).get("active_profile", "")).strip()
    )
    return profile or None


def _effective_runtime(raw: dict[str, Any], active_profile: str | None) -> dict[str, Any]:
    runtime = dict(raw.get("runtime", {}))
    profiles = runtime.get("profiles", {})
    base_runtime = {
        key: value
        for key, value in runtime.items()
        if key not in {"profiles", "active_profile"}
    }
    if not active_profile:
        return base_runtime
    if not isinstance(profiles, dict) or active_profile not in profiles:
        available = ", ".join(sorted(profiles)) if isinstance(profiles, dict) else "none"
        raise ValueError(
            f"Unknown runtime profile '{active_profile}'. Available profiles: {available}"
        )
    profile_runtime = profiles[active_profile]
    if not isinstance(profile_runtime, dict):
        raise ValueError(f"Runtime profile '{active_profile}' must be an object")
    effective = _merge_dicts(base_runtime, profile_runtime)
    effective["active_profile"] = active_profile
    return effective


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_dicts(current, value)
        else:
            merged[key] = value
    return merged
