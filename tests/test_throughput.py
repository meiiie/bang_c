"""Pure-speed levers: flash-attention/n_batch flags, the local_server provider, and
--workers concurrency. None of these may change answers — only wall-clock.
"""

from __future__ import annotations

import copy
import csv
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from hackaithon_c.config import load_config
from hackaithon_c.local_client import LocalLlamaConfig
from hackaithon_c.model_client import build_chat_client
from hackaithon_c.run import _solve_with_retry, main
from hackaithon_c.schema import Problem


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


class SpeedFlagTests(unittest.TestCase):
    def test_flash_attn_and_n_batch_default_off(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HACKC_LLAMACPP_FLASH_ATTN", None)
            os.environ.pop("HACKC_LLAMACPP_N_BATCH", None)
            local = LocalLlamaConfig.from_env(load_config())
        self.assertFalse(local.flash_attn)
        self.assertEqual(local.n_batch, 0)

    def test_flash_attn_and_n_batch_env_override(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"HACKC_LLAMACPP_FLASH_ATTN": "1", "HACKC_LLAMACPP_N_BATCH": "1024"},
        ):
            local = LocalLlamaConfig.from_env(load_config())
        self.assertTrue(local.flash_attn)
        self.assertEqual(local.n_batch, 1024)


class LocalServerProviderTests(unittest.TestCase):
    # NOTE: the active profile overlays runtime.provider, so the provider must be
    # selected explicitly (CLI --provider / HACKC_PROVIDER), same as real usage.

    def test_local_server_client_needs_no_api_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NVIDIA_API_KEY", None)
            os.environ.pop("HACKC_LOCAL_SERVER_URL", None)
            client = build_chat_client(load_config(), provider="local_server")
        # The contest model id rides along -> the family allowlist still applies.
        self.assertEqual(client.model, load_config().default_model)
        self.assertEqual(client._config.base_url, "http://127.0.0.1:8080/v1")

    def test_local_server_url_env_override(self) -> None:
        with mock.patch.dict(os.environ, {"HACKC_LOCAL_SERVER_URL": "http://127.0.0.1:9999/v1/"}):
            client = build_chat_client(load_config(), provider="local_server")
        self.assertEqual(client._config.base_url, "http://127.0.0.1:9999/v1")


class SolveWithRetryTests(unittest.TestCase):
    def test_dry_run_returns_prediction_and_no_retries(self) -> None:
        problem = Problem(qid="w1", question="Q?", choices=("a", "b", "c", "d"))
        prediction, retries = _solve_with_retry(
            problem,
            None,
            dry_run=True,
            verify=False,
            strategy="auto",
            fail_fast=False,
            config=load_config(),
        )
        self.assertIn(prediction.answer, problem.allowed_letters)
        self.assertEqual(retries, [])


class WorkersEndToEndTests(unittest.TestCase):
    def _run(self, workers: int) -> list[tuple[str, str]]:
        fixture = Path(__file__).parent / "fixtures" / "multilingual_gold.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "out"
            code = main(
                (
                    "--input", str(fixture),
                    "--output-dir", str(out_dir),
                    "--dry-run",
                    "--workers", str(workers),
                )
            )
            self.assertEqual(code, 0)
            with (out_dir / "pred.csv").open(encoding="utf-8") as handle:
                return [(row["qid"], row["answer"]) for row in csv.DictReader(handle)]

    def test_workers_preserve_order_and_answers(self) -> None:
        sequential = self._run(1)
        pooled = self._run(4)
        self.assertEqual(sequential, pooled)
        self.assertEqual(len(sequential), 24)


if __name__ == "__main__":
    unittest.main()
