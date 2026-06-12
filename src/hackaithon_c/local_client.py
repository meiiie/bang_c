from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import HarnessConfig


@dataclass(frozen=True)
class LocalLlamaConfig:
    model_id: str
    model_path: Path
    n_ctx: int = 8192
    n_gpu_layers: int = -1
    n_threads: int = 0
    chat_format: str | None = None
    flash_attn: bool = False
    n_batch: int = 0

    @classmethod
    def from_env(cls, config: HarnessConfig) -> "LocalLlamaConfig":
        model_id = os.environ.get("HACKC_LOCAL_MODEL_ID", config.default_model).strip()
        if not model_id:
            model_id = config.default_model
        model_path = Path(
            os.environ.get("HACKC_LOCAL_MODEL_PATH", config.local_model_path).strip()
            or config.local_model_path
        )
        chat_format = os.environ.get("HACKC_LLAMACPP_CHAT_FORMAT", config.local_chat_format).strip()
        flash_attn = os.environ.get(
            "HACKC_LLAMACPP_FLASH_ATTN", "1" if config.local_flash_attn else "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        return cls(
            model_id=model_id,
            model_path=model_path,
            n_ctx=int(os.environ.get("HACKC_LLAMACPP_N_CTX", str(config.local_n_ctx))),
            n_gpu_layers=int(
                os.environ.get("HACKC_LLAMACPP_N_GPU_LAYERS", str(config.local_n_gpu_layers))
            ),
            n_threads=int(
                os.environ.get("HACKC_LLAMACPP_N_THREADS", str(config.local_n_threads))
            ),
            chat_format=chat_format or None,
            flash_attn=flash_attn,
            n_batch=int(os.environ.get("HACKC_LLAMACPP_N_BATCH", str(config.local_n_batch))),
        )


class LocalLlamaChatClient:
    def __init__(self, config: LocalLlamaConfig) -> None:
        self._config = config
        self._llm: Any | None = None

    @property
    def model(self) -> str:
        return self._config.model_id

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 12,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        seed: int | None = None,
        letters: str | None = None,
    ) -> str:
        llm = self._load()
        kwargs: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            # None = the proven deterministic defaults; explicit values are used by
            # diversified sampling (seeded, so still reproducible run-to-run).
            "temperature": 0.0 if temperature is None else temperature,
            "top_p": 0.1 if top_p is None else top_p,
            "max_tokens": max_tokens,
        }
        if top_k is not None:
            kwargs["top_k"] = top_k
        if seed is not None:
            kwargs["seed"] = seed
        # Constrained decoding: when the caller names the valid option letters, force
        # the output to be exactly one of them via a GBNF grammar. Used by the repair
        # pass so a parse-fail can never reach the heuristic fallback (accuracy AND
        # contract robustness). Defensive: any grammar/llama version mismatch degrades
        # to unconstrained generation rather than crashing the run.
        grammar = _letter_grammar(letters)
        if grammar is not None:
            kwargs["grammar"] = grammar
        try:
            result = llm.create_chat_completion(**kwargs)
        except Exception:  # noqa: BLE001 - grammar unsupported -> retry unconstrained
            if "grammar" not in kwargs:
                raise
            kwargs.pop("grammar")
            result = llm.create_chat_completion(**kwargs)
        return _extract_chat_content(result)

    def _load(self) -> Any:
        if self._llm is not None:
            return self._llm
        if not self._config.model_path.exists():
            raise RuntimeError(
                "Local model file not found: "
                f"{self._config.model_path}. "
                "Set HACKC_LOCAL_MODEL_PATH or build the Gemma local Docker image."
            )
        try:
            from llama_cpp import Llama
        except ImportError as error:
            raise RuntimeError(
                "llama-cpp-python is required for provider=local_llamacpp. "
                "Install requirements-local.txt or use provider=nvidia for API experiments."
            ) from error

        kwargs: dict[str, Any] = {
            "model_path": str(self._config.model_path),
            "n_ctx": self._config.n_ctx,
            "n_gpu_layers": self._config.n_gpu_layers,
            "verbose": False,
        }
        if self._config.n_threads > 0:
            kwargs["n_threads"] = self._config.n_threads
        if self._config.chat_format:
            kwargs["chat_format"] = self._config.chat_format
        if self._config.flash_attn:
            kwargs["flash_attn"] = True
        if self._config.n_batch > 0:
            kwargs["n_batch"] = self._config.n_batch
        self._llm = Llama(**kwargs)
        return self._llm


def _letter_grammar(letters: str | None) -> Any | None:
    """Build a GBNF grammar that admits exactly one of the given option letters.

    Returns None when no letters are supplied or the grammar API is unavailable, so the
    caller silently runs unconstrained. Only A-Z letters are used (the option space),
    so the grammar string never needs escaping.
    """
    if not letters:
        return None
    valid = [ch for ch in letters if "A" <= ch <= "Z"]
    if not valid:
        return None
    try:
        from llama_cpp import LlamaGrammar
    except Exception:  # noqa: BLE001 - older/edge llama-cpp without grammar support
        return None
    alternation = " | ".join(f'"{ch}"' for ch in valid)
    try:
        return LlamaGrammar.from_string(f"root ::= {alternation}", verbose=False)
    except Exception:  # noqa: BLE001 - never let grammar construction break a run
        return None


def _extract_chat_content(result: Any) -> str:
    if isinstance(result, dict):
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and message.get("content") is not None:
                    return str(message["content"])
                if first.get("text") is not None:
                    return str(first["text"])
    return str(result)
