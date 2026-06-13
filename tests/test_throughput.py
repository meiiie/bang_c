"""Pure-speed levers: flash-attention/n_batch flags, the local_server provider, and
--workers concurrency. None of these may change answers — only wall-clock.
"""

from __future__ import annotations

import copy
import csv
import json
import os
import shlex
import shutil
import socket
import subprocess
import tempfile
import textwrap
import threading
import time
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

    def test_local_server_posts_openai_chat_completions(self) -> None:
        class Response:
            status_code = 200
            headers: dict[str, str] = {}

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"choices": [{"message": {"content": "B"}}]}

        with (
            mock.patch.dict(os.environ, {"HACKC_LOCAL_SERVER_URL": "http://127.0.0.1:9090/v1"}),
            mock.patch("requests.post", return_value=Response()) as post,
        ):
            client = build_chat_client(load_config(), provider="local_server")
            answer = client.complete(
                "system",
                "user",
                max_tokens=7,
                temperature=0,
                top_p=0.1,
                top_k=5,
                seed=42,
                letters="ABCD",
            )

        self.assertEqual(answer, "B")
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://127.0.0.1:9090/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer local")
        self.assertEqual(kwargs["json"]["messages"][1]["content"], "user")
        self.assertEqual(kwargs["json"]["max_tokens"], 7)
        self.assertEqual(kwargs["json"]["seed"], 42)
        self.assertNotIn("top_k", kwargs["json"])


class LocalServerEndToEndTests(unittest.TestCase):
    def test_harness_writes_pred_csv_against_openai_compatible_server(self) -> None:
        requests_seen: list[dict[str, object]] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
                if self.path != "/health":
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")

            def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                requests_seen.append({"path": self.path, "payload": payload})
                body = json.dumps({"choices": [{"message": {"content": "B"}}]}).encode(
                    "utf-8"
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                input_path = temp_path / "input.json"
                output_dir = temp_path / "out"
                input_path.write_text(
                    json.dumps(
                        [
                            {
                                "qid": "stub_1",
                                "question": "Choose the second option.",
                                "choices": ["Alpha", "Beta", "Gamma", "Delta"],
                            },
                            {
                                "qid": "stub_2",
                                "question": "Again choose the second option.",
                                "choices": ["One", "Two", "Three", "Four"],
                            },
                        ],
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                base_url = f"http://127.0.0.1:{server.server_port}/v1"
                with mock.patch.dict(
                    os.environ,
                    {
                        "HACKC_LOCAL_SERVER_URL": base_url,
                        "HACKC_API_KEY": "",
                        "NVIDIA_API_KEY": "",
                    },
                    clear=False,
                ):
                    code = main(
                        (
                            "--input",
                            str(input_path),
                            "--output-dir",
                            str(output_dir),
                            "--provider",
                            "local_server",
                            "--strategy",
                            "direct",
                            "--workers",
                            "2",
                        )
                    )

                self.assertEqual(code, 0)
                with (output_dir / "pred.csv").open(encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(
            rows,
            [{"qid": "stub_1", "answer": "B"}, {"qid": "stub_2", "answer": "B"}],
        )
        self.assertEqual([request["path"] for request in requests_seen], ["/v1/chat/completions"] * 2)
        for request in requests_seen:
            payload = request["payload"]
            self.assertEqual(payload["model"], load_config().default_model)
            self.assertFalse(payload["stream"])


class MtpServerScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = (Path.cwd() / "scripts" / "gpu" / "run_mtp_server.sh").read_text(
            encoding="utf-8"
        )

    def test_mtp_script_requires_owner_signoff_before_gpu_work(self) -> None:
        self.assertIn('OWNER_SIGNOFF="${OWNER_SIGNOFF:-0}"', self.script)
        self.assertIn("Refusing to start GPU/model work", self.script)
        self.assertLess(
            self.script.index('OWNER_SIGNOFF="${OWNER_SIGNOFF:-0}"'),
            self.script.index("nvidia-smi"),
        )
        self.assertLess(
            self.script.index('OWNER_SIGNOFF="${OWNER_SIGNOFF:-0}"'),
            self.script.index("install build tools"),
        )

    def test_mtp_script_uses_repeated_median_measurements(self) -> None:
        self.assertIn('MEASURE_REQUESTS="${MEASURE_REQUESTS:-3}"', self.script)
        self.assertIn('for j in $(seq 1 "$MEASURE_REQUESTS"); do', self.script)
        self.assertIn("def median(values):", self.script)
        self.assertIn('"speedup_vs_baseline_median": speedup', self.script)

    def test_mtp_script_can_export_representative_harness_prompt_before_gpu_work(self) -> None:
        self.assertIn('N_PREDICT="${N_PREDICT:-2048}"', self.script)
        self.assertIn('BENCH_ENDPOINT="${BENCH_ENDPOINT:-chat}"', self.script)
        self.assertIn('BENCH_INPUT_PATH="${BENCH_INPUT_PATH:-}"', self.script)
        self.assertIn("export_mtp_benchmark_prompt.py", self.script)
        self.assertIn("--prompt-out \"$OUT_DIR/benchmark-prompt.txt\"", self.script)
        self.assertIn("--messages-out \"$OUT_DIR/benchmark-messages.json\"", self.script)
        self.assertIn("--metadata-out \"$OUT_DIR/benchmark-prompt-metadata.json\"", self.script)
        self.assertIn("/v1/chat/completions", self.script)
        self.assertIn('"max_tokens": n_predict', self.script)
        self.assertIn('"PROMPT_SOURCE"', self.script)
        self.assertLess(
            self.script.rindex("prepare_benchmark_prompt"),
            self.script.index("nvidia-smi"),
        )

    def test_mtp_script_checks_port_before_gpu_or_build_work(self) -> None:
        self.assertIn("ensure_port_free()", self.script)
        self.assertIn('ensure_port_free "$PORT"', self.script)
        first_check = self.script.index('ensure_port_free "$PORT"')
        self.assertLess(first_check, self.script.index("nvidia-smi"))
        self.assertLess(first_check, self.script.index("install build tools"))

    def test_mtp_script_fails_on_non_lossless_content_by_default(self) -> None:
        self.assertIn('REQUIRE_CONTENT_MATCH="${REQUIRE_CONTENT_MATCH:-1}"', self.script)
        self.assertIn("content did not match baseline", self.script)
        self.assertLess(
            self.script.index('"verdict": "fail"'),
            self.script.index('touch "$WORKSPACE/SRV_DONE"'),
        )

    def test_mtp_script_keeps_log_wording_checks_warning_only_by_default(self) -> None:
        self.assertIn('REQUIRE_SPEC_INIT="${REQUIRE_SPEC_INIT:-0}"', self.script)
        self.assertIn('REQUIRE_DRAFT_ACCEPTANCE="${REQUIRE_DRAFT_ACCEPTANCE:-0}"', self.script)
        self.assertIn("warnings.append(message)", self.script)
        self.assertIn("if require_spec_init:", self.script)
        self.assertIn("if label != \"baseline\" and require_draft_acceptance", self.script)

    def test_mtp_script_uses_current_llama_mtp_flags_and_child_cleanup(self) -> None:
        for flag in (
            "--spec-type draft-mtp",
            "--spec-draft-n-max",
            "--spec-draft-type-k f16",
            "--spec-draft-type-v f16",
            "--spec-draft-ngl 999",
            "--spec-draft-device CUDA0",
            "--model-draft",
        ):
            self.assertIn(flag, self.script)
        self.assertIn('kill "$SERVER_PID"', self.script)
        self.assertNotIn("pkill", self.script)


class NekoEntrypointServerModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = (Path.cwd() / "docker" / "neko-entrypoint.sh").read_text(
            encoding="utf-8"
        )

    def test_server_mode_requires_model_files_and_llama_server(self) -> None:
        self.assertIn('if [[ "${NEKO_LOCAL_SERVER_MODE:-}" == "1" ]]', self.script)
        self.assertIn('command -v "$server_bin"', self.script)
        self.assertIn('[[ ! -f "$main_model" ]]', self.script)
        self.assertIn('[[ ! -f "$draft_model" ]]', self.script)
        self.assertIn("NEKO_LOCAL_SERVER_HEALTH_TIMEOUT_SECONDS must be a positive integer", self.script)
        self.assertLess(
            self.script.index('command -v "$server_bin"'),
            self.script.index('"$server_bin" \\'),
        )

    def test_server_mode_starts_draft_mtp_and_waits_for_health(self) -> None:
        for marker in (
            '--model-draft "$draft_model"',
            "--spec-type draft-mtp",
            '--spec-draft-n-max "$draft_n_max"',
            "--spec-draft-type-k f16",
            "--spec-draft-type-v f16",
            'health_url="http://${host}:${port}/health"',
            "is_local_server_healthy()",
            "llama-server did not become healthy",
        ):
            self.assertIn(marker, self.script)
        self.assertLess(
            self.script.index('--model-draft "$draft_model"'),
            self.script.index("export HACKC_PROVIDER=local_server"),
        )

    def test_server_mode_runs_harness_through_local_server_provider(self) -> None:
        self.assertIn('export HACKC_PROVIDER=local_server', self.script)
        self.assertIn('export HACKC_LOCAL_SERVER_URL="$base_url"', self.script)
        self.assertIn("--provider local_server", self.script)
        self.assertIn('--workers "$workers"', self.script)
        self.assertIn("cleanup_local_server()", self.script)
        self.assertIn("trap cleanup_local_server EXIT INT TERM", self.script)
        self.assertIn('NEKO_LOCAL_SERVER_PID="$!"', self.script)
        self.assertIn('kill "$NEKO_LOCAL_SERVER_PID"', self.script)

    def test_server_mode_smoke_waits_runs_harness_and_cleans_up(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash is not available for entrypoint smoke")
        python_probe = subprocess.run(
            ["bash", "-c", "python3 -c 'import requests'"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if python_probe.returncode != 0:
            self.skipTest("bash python3 with requests is not available for entrypoint smoke")

        repo = Path.cwd()
        with tempfile.TemporaryDirectory(prefix="entrypoint-smoke-", dir=repo) as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.json"
            output_dir = temp_path / "out"
            main_model = temp_path / "main.gguf"
            draft_model = temp_path / "draft.gguf"
            log_path = temp_path / "fake-server.log"
            fake_server = temp_path / "fake-llama-server"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "qid": "entry_1",
                            "question": "Choose the second option.",
                            "choices": ["Alpha", "Beta", "Gamma", "Delta"],
                        },
                        {
                            "qid": "entry_2",
                            "question": "Again choose the second option.",
                            "choices": ["One", "Two", "Three", "Four"],
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            main_model.write_text("main", encoding="utf-8")
            draft_model.write_text("draft", encoding="utf-8")
            fake_server_source = textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                host="127.0.0.1"
                port="8080"
                while [[ "$#" -gt 0 ]]; do
                  case "$1" in
                    --host) host="$2"; shift 2 ;;
                    --port) port="$2"; shift 2 ;;
                    *) shift ;;
                  esac
                done
                exec "${NEKO_PYTHON_BIN:-python}" - "$host" "$port" "$NEKO_FAKE_SERVER_LOG" <<'PY'
                import json
                import signal
                import sys
                from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

                host = sys.argv[1]
                port = int(sys.argv[2])
                log_path = sys.argv[3]

                def log(line):
                    with open(log_path, "a", encoding="utf-8") as handle:
                        handle.write(line + "\\n")

                class Handler(BaseHTTPRequestHandler):
                    def do_GET(self):
                        log("GET " + self.path)
                        if self.path != "/health":
                            self.send_response(404)
                            self.end_headers()
                            return
                        body = b"OK"
                        self.send_response(200)
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)

                    def do_POST(self):
                        length = int(self.headers.get("Content-Length", "0"))
                        self.rfile.read(length)
                        log("POST " + self.path)
                        body = json.dumps(
                            {"choices": [{"message": {"content": "B"}}]}
                        ).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)

                    def log_message(self, format, *args):
                        return None

                server = ThreadingHTTPServer((host, port), Handler)

                def stop(signum, frame):
                    log("SIGNAL " + str(signum))
                    raise SystemExit(0)

                signal.signal(signal.SIGTERM, stop)
                try:
                    log("START " + host + ":" + str(port))
                    server.serve_forever(poll_interval=0.1)
                finally:
                    log("EXIT")
                    server.server_close()
                PY
                """
            )
            with fake_server.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(fake_server_source)
            fake_server.chmod(0o755)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = str(sock.getsockname()[1])

            def rel(path: Path) -> str:
                return path.relative_to(repo).as_posix()

            shell_env = {
                "NEKO_LOCAL_SERVER_MODE": "1",
                "NEKO_LLAMA_SERVER_BIN": rel(fake_server),
                "NEKO_MAIN_MODEL_PATH": rel(main_model),
                "NEKO_MTP_DRAFT_MODEL_PATH": rel(draft_model),
                "NEKO_LOCAL_SERVER_PORT": port,
                "NEKO_LOCAL_SERVER_HEALTH_TIMEOUT_SECONDS": "10",
                "NEKO_FAKE_SERVER_LOG": rel(log_path),
                "NEKO_PYTHON_BIN": "python3",
                "PYTHONPATH": "src",
            }
            exports = "; ".join(
                f"export {key}={shlex.quote(value)}"
                for key, value in shell_env.items()
            )
            entrypoint_args = [
                "docker/neko-entrypoint.sh",
                "--input",
                rel(input_path),
                "--output-dir",
                rel(output_dir),
                "--strategy",
                "direct",
                "--workers",
                "2",
            ]
            command = (
                exports
                + "; bash "
                + " ".join(shlex.quote(arg) for arg in entrypoint_args)
            )
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with (output_dir / "pred.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            log_text = log_path.read_text(encoding="utf-8")
            server_closed = False
            for _ in range(20):
                try:
                    connection = socket.create_connection(
                        ("127.0.0.1", int(port)),
                        timeout=0.1,
                    )
                except OSError:
                    server_closed = True
                    break
                else:
                    connection.close()
                    time.sleep(0.1)

        self.assertEqual(
            rows,
            [{"qid": "entry_1", "answer": "B"}, {"qid": "entry_2", "answer": "B"}],
        )
        self.assertIn("GET /health", log_text)
        self.assertEqual(log_text.count("POST /v1/chat/completions"), 2)
        self.assertTrue(server_closed, log_text)


class NekoEntrypointFallbackTests(unittest.TestCase):
    """The MTP speed lever must never be able to zero the Accuracy score: when
    llama-server cannot run, the entrypoint falls back to the in-process
    local_llamacpp provider and still produces a valid pred.csv."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = (Path.cwd() / "docker" / "neko-entrypoint.sh").read_text(
            encoding="utf-8"
        )

    def test_mtp_default_n_max_is_two(self) -> None:
        # n-max=2 gave the best measured speedup (1.37x) on the 26B-A4B MoE.
        self.assertIn('draft_n_max="${NEKO_MTP_DRAFT_N_MAX:-2}"', self.script)

    def test_main_model_uses_flash_attention_and_f16_kv(self) -> None:
        # Mirrors the flags the 1.37x was measured on (run_mtp_server.sh).
        for marker in ("-fa on", "-ctk f16", "-ctv f16"):
            self.assertIn(marker, self.script)

    def test_server_mode_falls_back_to_local_llamacpp(self) -> None:
        self.assertIn("if run_local_server_mode", self.script)
        self.assertIn("export HACKC_PROVIDER=local_llamacpp", self.script)
        self.assertIn("unset HACKC_LOCAL_SERVER_URL", self.script)
        # the fallback export must come AFTER the server-mode export so it wins
        self.assertLess(
            self.script.index("export HACKC_PROVIDER=local_server"),
            self.script.index("export HACKC_PROVIDER=local_llamacpp"),
        )

    def test_fallback_smoke_produces_predictions_without_llama_server(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash is not available for fallback smoke")
        probe = subprocess.run(
            ["bash", "-c", "PYTHONPATH=src python3 -c 'import hackaithon_c'"],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        if probe.returncode != 0:
            self.skipTest("bash python3 cannot import hackaithon_c for fallback smoke")

        repo = Path.cwd()
        with tempfile.TemporaryDirectory(prefix="fallback-smoke-", dir=repo) as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.json"
            output_dir = temp_path / "out"
            input_path.write_text(
                json.dumps(
                    [
                        {"qid": "fb_1", "question": "Q1?", "choices": ["a", "b", "c", "d"]},
                        {"qid": "fb_2", "question": "Q2?", "choices": ["a", "b", "c", "d"]},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            def rel(path: Path) -> str:
                return path.relative_to(repo).as_posix()

            shell_env = {
                "NEKO_LOCAL_SERVER_MODE": "1",
                # missing binary -> run_local_server_mode returns 1 -> fallback path
                "NEKO_LLAMA_SERVER_BIN": "/nonexistent/llama-server",
                "NEKO_PYTHON_BIN": "python3",
                "PYTHONPATH": "src",
            }
            exports = "; ".join(
                f"export {key}={shlex.quote(value)}" for key, value in shell_env.items()
            )
            entrypoint_args = [
                "docker/neko-entrypoint.sh",
                "--input", rel(input_path),
                "--output-dir", rel(output_dir),
                "--dry-run",
                "--strategy", "direct",
            ]
            command = exports + "; bash " + " ".join(
                shlex.quote(arg) for arg in entrypoint_args
            )
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "falling back to in-process local_llamacpp", result.stderr
            )
            with (output_dir / "pred.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["qid"] for row in rows], ["fb_1", "fb_2"])
            for row in rows:
                self.assertIn(row["answer"], {"A", "B", "C", "D"})


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
