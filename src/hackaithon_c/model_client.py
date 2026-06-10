from __future__ import annotations

import os
from typing import Protocol

from .config import HarnessConfig
from .local_client import LocalLlamaChatClient, LocalLlamaConfig
from .nvidia_client import NvidiaChatClient, NvidiaConfig


class ChatClient(Protocol):
    @property
    def model(self) -> str:
        ...

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 12) -> str:
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
            )
        )
    raise ValueError(
        f"Unknown provider '{selected_provider}'. Use local_llamacpp or nvidia."
    )
