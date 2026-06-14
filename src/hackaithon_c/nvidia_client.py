from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "google/gemma-4-31b-it"


@dataclass(frozen=True)
class NvidiaConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: int = 90
    max_retries: int = 6
    retry_base_delay_seconds: float = 1.5
    retry_max_delay_seconds: float = 30.0
    # Gemma's chat template has no real system role. llama-server (local_server) drops/
    # mishandles a separate system message -> reasoning instructions lost -> short answers.
    # Set True for local_server to merge system into the user turn (what llama-cpp-python's
    # in-process gemma chat_format does), restoring the proven self-consistency behavior.
    merge_system_into_user: bool = False

    @classmethod
    def from_env(
        cls,
        *,
        default_base_url: str = DEFAULT_BASE_URL,
        default_model: str = DEFAULT_MODEL,
        default_timeout_seconds: int = 90,
        default_max_retries: int = 6,
        default_retry_base_delay_seconds: float = 1.5,
        default_retry_max_delay_seconds: float = 30.0,
        default_api_key: str = "",
    ) -> "NvidiaConfig":
        # Key precedence: env (HACKC_API_KEY, then the NVIDIA_API_KEY back-compat alias)
        # wins, then `default_api_key` (from ~/.neko-core/config.json's "api_key"). The
        # provider-neutral name is first because the OpenAI-compatible client also serves
        # other dev profiles (e.g. FPT AI Marketplace).
        api_key = (
            os.environ.get("HACKC_API_KEY")
            or os.environ.get("NVIDIA_API_KEY")
            or default_api_key
            or ""
        ).strip()
        if not api_key:
            raise RuntimeError(
                "No API key found. Set HACKC_API_KEY (or NVIDIA_API_KEY), or add "
                '"api_key" under "runtime" in ~/.neko-core/config.json '
                "(run `neko --init-user`). Not needed for local providers or --dry-run."
            )
        return cls(
            api_key=api_key,
            base_url=os.environ.get("NVIDIA_BASE_URL", default_base_url).rstrip("/"),
            model=os.environ.get("HACKC_LLM_MODEL", default_model).strip() or default_model,
            timeout_seconds=int(os.environ.get("HACKC_TIMEOUT_SECONDS", str(default_timeout_seconds))),
            max_retries=int(os.environ.get("HACKC_MAX_RETRIES", str(default_max_retries))),
            retry_base_delay_seconds=float(
                os.environ.get(
                    "HACKC_RETRY_BASE_DELAY_SECONDS",
                    str(default_retry_base_delay_seconds),
                )
            ),
            retry_max_delay_seconds=float(
                os.environ.get(
                    "HACKC_RETRY_MAX_DELAY_SECONDS",
                    str(default_retry_max_delay_seconds),
                )
            ),
        )


class NvidiaChatClient:
    def __init__(self, config: NvidiaConfig) -> None:
        self._config = config

    @property
    def model(self) -> str:
        return self._config.model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 12,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,  # accepted for protocol parity; OpenAI-compat APIs ignore it
        seed: int | None = None,
        letters: str | None = None,  # accepted for protocol parity; GBNF is local-only
    ) -> str:
        import requests

        if self._config.merge_system_into_user and system_prompt:
            messages = [{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": 0.0 if temperature is None else temperature,
            "top_p": 0.1 if top_p is None else top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if seed is not None:
            payload["seed"] = seed
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._config.base_url}/chat/completions"
        last_error: Exception | None = None
        retryable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(self._config.max_retries + 1):
            response = None
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._config.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"])
            except requests.HTTPError as error:
                last_error = error
                status_code = response.status_code if response is not None else None
                if status_code not in retryable_statuses or attempt >= self._config.max_retries:
                    break
                time.sleep(_retry_delay_seconds(attempt, response, self._config))
            except Exception as error:  # noqa: BLE001 - retry boundary
                last_error = error
                if attempt >= self._config.max_retries:
                    break
                time.sleep(_retry_delay_seconds(attempt, response, self._config))
        raise RuntimeError(f"NVIDIA chat completion failed: {last_error}") from last_error


def _retry_delay_seconds(
    attempt: int,
    response: Any | None,
    config: NvidiaConfig,
) -> float:
    retry_after = _parse_retry_after(response)
    if retry_after is not None:
        return min(config.retry_max_delay_seconds, retry_after)
    exponential = config.retry_base_delay_seconds * (2**attempt)
    return min(config.retry_max_delay_seconds, exponential)


def _parse_retry_after(response: Any | None) -> float | None:
    if response is None:
        return None
    raw_value = getattr(response, "headers", {}).get("Retry-After")
    if raw_value is None:
        return None
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed
