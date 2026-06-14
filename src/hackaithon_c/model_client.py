from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from .config import HarnessConfig
from .local_client import LocalLlamaChatClient, LocalLlamaConfig
from .nvidia_client import NvidiaChatClient, NvidiaConfig


class ChatClient(Protocol):
    @property
    def model(self) -> str:
        ...

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
        """temperature/top_p/seed default to None = the provider's deterministic
        defaults (temperature 0). Diversified sampling passes explicit values; a
        fixed seed keeps temp>0 sampling reproducible run-to-run. `letters`, when set,
        constrains the output to exactly one of the named option letters (the local
        runtime enforces it via a GBNF grammar; API providers may ignore it)."""
        ...


def effective_provider(config: HarnessConfig, requested_provider: str | None = None) -> str:
    provider = (requested_provider or os.environ.get("HACKC_PROVIDER") or config.provider).strip()
    return provider or "local_llamacpp"


def build_chat_client(
    config: HarnessConfig,
    *,
    provider: str | None = None,
) -> ChatClient:
    selected_provider = effective_provider(config, provider)
    if selected_provider == "local_llamacpp":
        return LocalLlamaChatClient(LocalLlamaConfig.from_env(config))
    if selected_provider == "nvidia":
        return NvidiaChatClient(
            NvidiaConfig.from_env(
                default_base_url=config.base_url,
                default_model=config.api_model,
                default_timeout_seconds=config.timeout_seconds,
                default_max_retries=config.max_retries,
                default_retry_base_delay_seconds=config.retry_base_delay_seconds,
                default_retry_max_delay_seconds=config.retry_max_delay_seconds,
                default_api_key=config.api_key,
            )
        )
    if selected_provider == "local_server":
        # An in-container llama.cpp `llama-server` speaking the OpenAI-compatible
        # protocol on localhost. Same offline/self-contained guarantee as
        # local_llamacpp, but the server's continuous batching lets the harness
        # solve several questions concurrently (--workers). No API key involved;
        # llama-server ignores Authorization.
        return NvidiaChatClient(
            NvidiaConfig(
                api_key="local",
                base_url=os.environ.get("HACKC_LOCAL_SERVER_URL", config.local_server_url).rstrip("/"),
                model=config.default_model,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries,
                retry_base_delay_seconds=config.retry_base_delay_seconds,
                retry_max_delay_seconds=config.retry_max_delay_seconds,
                # Gemma has no system role; merge it into the user turn so llama-server
                # keeps the reasoning instructions (matches the in-process path).
                merge_system_into_user=True,
            )
        )
    raise ValueError(
        f"Unknown provider '{selected_provider}'. Use local_llamacpp, nvidia, or local_server."
    )


def build_challenger_client(config: HarnessConfig) -> ChatClient | None:
    """Build the optional second-model (challenger) client for cross-model ensembles.

    Returns None when no challenger is configured — every caller must degrade
    gracefully. Only the local provider is supported for the contest path (the
    container is offline); the model file must be baked into the image.
    """
    provider = config.challenger_provider
    model_path = config.challenger_model_path
    if not provider or not model_path:
        return None
    if provider != "local_llamacpp":
        raise ValueError(
            f"Unsupported challenger_provider '{provider}'. Use local_llamacpp."
        )
    return LocalLlamaChatClient(
        LocalLlamaConfig(
            model_id=config.challenger_model_id or model_path,
            model_path=Path(model_path),
            n_ctx=config.local_n_ctx,
            n_gpu_layers=config.local_n_gpu_layers,
            n_threads=config.local_n_threads,
            chat_format=None,
        )
    )
