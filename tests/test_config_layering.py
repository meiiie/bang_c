from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from hackaithon_c.config import HarnessConfig, load_config
from hackaithon_c.nvidia_client import NvidiaConfig
from hackaithon_c.project import USER_CONFIG_TEMPLATE, init_user_config


class ApiKeyPropertyTests(unittest.TestCase):
    def test_api_key_read_from_runtime(self) -> None:
        cfg = HarnessConfig(raw={"runtime": {"api_key": "  secret-123 "}}, path=Path("x"))
        self.assertEqual(cfg.api_key, "secret-123")

    def test_api_key_defaults_empty(self) -> None:
        cfg = HarnessConfig(raw={"runtime": {}}, path=Path("x"))
        self.assertEqual(cfg.api_key, "")


class NvidiaKeyPrecedenceTests(unittest.TestCase):
    def _clean_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("HACKC_API_KEY", None)
        env.pop("NVIDIA_API_KEY", None)
        return env

    def test_env_wins_over_config_key(self) -> None:
        env = self._clean_env()
        env["HACKC_API_KEY"] = "env-key"
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = NvidiaConfig.from_env(default_api_key="config-key")
        self.assertEqual(cfg.api_key, "env-key")

    def test_config_key_used_when_no_env(self) -> None:
        with mock.patch.dict(os.environ, self._clean_env(), clear=True):
            cfg = NvidiaConfig.from_env(default_api_key="config-key")
        self.assertEqual(cfg.api_key, "config-key")

    def test_missing_key_raises_helpful_error(self) -> None:
        with mock.patch.dict(os.environ, self._clean_env(), clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                NvidiaConfig.from_env(default_api_key="")
        self.assertIn(".neko-core/config.json", str(ctx.exception))


class LayeredConfigTests(unittest.TestCase):
    def test_partial_project_overlay_merges_onto_default(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / ".neko-core").mkdir()
            (tdp / ".neko-core" / "config.json").write_text(
                json.dumps(
                    {"runtime": {"api_key": "proj-key", "active_profile": "nvidia-gemma31b-api"}}
                ),
                encoding="utf-8",
            )
            old_cwd = os.getcwd()
            # Point HOME at an empty dir so a real ~/.neko-core cannot taint the test.
            with mock.patch.object(Path, "home", return_value=tdp / "empty-home"):
                try:
                    os.chdir(tdp)
                    cfg = load_config()
                finally:
                    os.chdir(old_cwd)
            # Overlay values applied...
            self.assertEqual(cfg.api_key, "proj-key")
            self.assertEqual(cfg.active_profile, "nvidia-gemma31b-api")
            self.assertEqual(cfg.provider, "nvidia")
            # ...while untouched required sections still come from the baked default.
            self.assertTrue(cfg.thresholds)
            self.assertTrue(cfg.rubric)

    def test_no_overlay_matches_plain_default(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td)
            old_cwd = os.getcwd()
            with mock.patch.object(Path, "home", return_value=tdp / "empty-home"):
                try:
                    os.chdir(tdp)
                    cfg = load_config()
                finally:
                    os.chdir(old_cwd)
            # Default contest provider is local, key empty — no env/file required.
            self.assertEqual(cfg.api_key, "")
            self.assertTrue(cfg.default_model)


class InitUserConfigTests(unittest.TestCase):
    def test_scaffolds_home_config_and_reloads(self) -> None:
        with TemporaryDirectory() as td:
            tdp = Path(td)
            with mock.patch.object(Path, "home", return_value=tdp):
                result = init_user_config()
                self.assertTrue(result.created)
                self.assertTrue(result.config_path.exists())
                self.assertEqual(result.config_path, tdp / ".neko-core" / "config.json")
                # Idempotent without --force.
                again = init_user_config()
                self.assertFalse(again.created)
        self.assertEqual(USER_CONFIG_TEMPLATE["runtime"]["active_profile"], "nvidia-gemma31b-api")


if __name__ == "__main__":
    unittest.main()
