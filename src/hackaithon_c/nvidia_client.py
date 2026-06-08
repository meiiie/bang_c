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
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "NvidiaConfig":
        api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY is required unless --dry-run is used")
        return cls(
            api_key=api_key,
            base_url=os.environ.get("NVIDIA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=os.environ.get("HACKC_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            timeout_seconds=int(os.environ.get("HACKC_TIMEOUT_SECONDS", "90")),
            max_retries=int(os.environ.get("HACKC_MAX_RETRIES", "2")),
        )


class NvidiaChatClient:
    def __init__(self, config: NvidiaConfig) -> None:
        self._config = config

    @property
    def model(self) -> str:
        return self._config.model

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 12) -> str:
        import requests

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "top_p": 0.1,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._config.base_url}/chat/completions"
        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._config.timeout_seconds,
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"])
            except Exception as error:  # noqa: BLE001 - retry boundary
                last_error = error
                if attempt >= self._config.max_retries:
                    break
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"NVIDIA chat completion failed: {last_error}") from last_error
