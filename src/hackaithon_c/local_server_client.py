"""Client for an in-container llama.cpp `llama-server` driven via its RAW `/completion`
endpoint — the parity fix for the MTP (`local_server`) path.

The earlier `local_server` client posted to `/v1/chat/completions`, which makes the server apply
its OWN chat template; that drifted from the proven in-process Gemma formatting and collapsed the
answer-fallback rate to ~75%. Here we instead build the EXACT official Gemma-4 prompt ourselves and
post it to `/completion`, bypassing the server template entirely.

Official Gemma-4 format (ai.google.dev/gemma/docs/core/prompt-structure): there is NO system role;
system instructions go INTO the user turn. The prompt is:

    <start_of_turn>user
    {system}

    {user}<end_of_turn>
    <start_of_turn>model

The server adds BOS per the GGUF; stop on `<end_of_turn>`. This is byte-stable and independent of
the server's template handling, so MTP (`--spec-type draft-mtp`) speeds the run without touching
accuracy. If the server is unhealthy the entrypoint falls back to the in-process path (a speed lever
must never zero the Accuracy score)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

GEMMA_TURN_STOP = "<end_of_turn>"


def build_gemma_prompt(system_prompt: str, user_prompt: str) -> str:
    """The exact official Gemma-4 instruction prompt. System (if any) is merged into the
    user turn with a blank line, matching Google's documented format."""
    system = (system_prompt or "").strip()
    user = user_prompt or ""
    content = f"{system}\n\n{user}" if system else user
    return f"<start_of_turn>user\n{content}{GEMMA_TURN_STOP}\n<start_of_turn>model\n"


def _letter_grammar(letters: str | None) -> str | None:
    """GBNF that admits exactly one option letter (llama-server `/completion` accepts a
    grammar string), mirroring the in-process GBNF repair constraint."""
    if not letters:
        return None
    valid = [ch for ch in letters if "A" <= ch <= "Z"]
    if not valid:
        return None
    return "root ::= " + " | ".join(f'"{ch}"' for ch in valid)


@dataclass(frozen=True)
class LocalServerConfig:
    base_url: str  # the llama-server root (without /v1); /completion is posted under it
    model: str
    timeout_seconds: int = 90
    max_retries: int = 6
    retry_base_delay_seconds: float = 1.5
    retry_max_delay_seconds: float = 30.0


def _completion_root(base_url: str) -> str:
    # HACKC_LOCAL_SERVER_URL is conventionally ".../v1"; /completion lives at the server root.
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return root


class LocalServerChatClient:
    def __init__(self, config: LocalServerConfig) -> None:
        self._config = config
        self._url = _completion_root(config.base_url) + "/completion"

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
        top_k: int | None = None,
        seed: int | None = None,
        letters: str | None = None,
    ) -> str:
        import requests

        payload: dict[str, Any] = {
            "prompt": build_gemma_prompt(system_prompt, user_prompt),
            "n_predict": max_tokens,
            "temperature": 0.0 if temperature is None else temperature,
            "top_p": 0.1 if top_p is None else top_p,
            "stop": [GEMMA_TURN_STOP],
            "cache_prompt": True,
        }
        if top_k is not None:
            payload["top_k"] = top_k
        if seed is not None:
            payload["seed"] = seed
        grammar = _letter_grammar(letters)
        if grammar is not None:
            payload["grammar"] = grammar
        headers = {"Content-Type": "application/json"}
        last_error: Exception | None = None
        retryable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(self._config.max_retries + 1):
            response = None
            try:
                response = requests.post(
                    self._url, headers=headers, json=payload, timeout=self._config.timeout_seconds
                )
                response.raise_for_status()
                return str(response.json().get("content", ""))
            except requests.HTTPError as error:
                last_error = error
                status_code = response.status_code if response is not None else None
                if status_code not in retryable_statuses or attempt >= self._config.max_retries:
                    break
                time.sleep(min(self._config.retry_max_delay_seconds,
                               self._config.retry_base_delay_seconds * (2 ** attempt)))
            except Exception as error:  # noqa: BLE001 - retry boundary
                last_error = error
                if attempt >= self._config.max_retries:
                    break
                time.sleep(min(self._config.retry_max_delay_seconds,
                               self._config.retry_base_delay_seconds * (2 ** attempt)))
        raise RuntimeError(f"local_server /completion failed: {last_error}") from last_error
