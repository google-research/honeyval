"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import atexit
import json
import logging
import os
import secrets
import shutil
import subprocess
import tempfile
from logging import Logger
from pathlib import Path
from time import sleep, time
from typing import IO

from src.utils.constants import DOCKER_BRIDGE_GATEWAY
from src.utils.logger import MetadataLogger
from src.utils.port_finder import find_free_ports, is_port_in_use


class LiteLLMProxy:
    """
    Manages a LiteLLM proxy logging every request/response as JSONL.
    """

    def __init__(
        self,
        model_name: str,
        metadata_log_path: Path,
        logger: Logger | None = None,
        host: str = "127.0.0.1",
        port: int | None = None,
        force_port: bool = False,
    ) -> None:
        allowed_hosts = {"127.0.0.1", "localhost", DOCKER_BRIDGE_GATEWAY}
        if host not in allowed_hosts:
            raise ValueError(
                f"Proxy host must be one of {allowed_hosts} (got host={host!r})."
            )

        self.api_key: str = secrets.token_urlsafe(32)

        self._model_name = model_name
        self._metadata_log_path = Path(metadata_log_path)
        self._logger = logger
        self._host = host
        self._requested_port = port
        self._force_port = force_port
        self.port: int | None = None  # resolved in serve()

        self._process: subprocess.Popen | None = None
        self._config_path: Path | None = None
        self._config_dir: Path | None = None
        self._log_fp: IO[str] | None = None

        atexit.register(self.stop)

    # ---- config ----

    def _build_config(self) -> dict:
        if self._logger:
            self._logger.debug(
                f"Building LiteLLM config dictionary for model: {self._model_name}"
            )

        litellm_params: dict = {"model": self._model_name}

        if "vertex" in self._model_name:
            if "vertex_location" not in litellm_params:
                litellm_params["vertex_location"] = "global"
        elif "anthropic" in self._model_name or "claude" in self._model_name:
            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not anthropic_api_key:
                raise ValueError(
                    "Missing anthropic api key environment variable: ANTHROPIC_API_KEY"
                )
        elif "together_ai" in self._model_name:
            together_api_key = os.environ.get("TOGETHERAI_API_KEY")
            if not together_api_key:
                raise ValueError(
                    "Missing together.ai api key environment variable: TOGETHERAI_API_KEY"
                )
        else:
            bifrost_url = os.environ.get("BIFROST_URL")
            bifrost_key = os.environ.get("BIFROST_KEY")
            if bifrost_url:
                litellm_params["api_base"] = bifrost_url
            if bifrost_key:
                litellm_params["api_key"] = bifrost_key
            # Force openai routing like litellm_erb does
            if not litellm_params["model"].startswith("openai/"):
                litellm_params["model"] = "openai/" + litellm_params["model"]

        # User-facing model name (strip provider prefix)
        clean_name = (
            self._model_name.split("/", 1)[-1]
            if "/" in self._model_name
            else self._model_name
        )

        return {
            "model_list": [
                {
                    "model_name": clean_name,
                    "litellm_params": litellm_params,
                },
            ],
            "litellm_settings": {
                "drop_params": True,
                "callbacks": "litellm_logger.proxy_handler_instance",
            },
            "general_settings": {
                "drop_params": True,
                "master_key": self.api_key,
            },
        }

    def _write_config(self) -> Path:
        """Write proxy config and copy the logger module next to it."""
        self._config_dir = Path(tempfile.mkdtemp(prefix="litellm_proxy_"))

        config_path = self._config_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(self._build_config(), f, indent=2)

        # litellm resolves callback modules relative to the config file dir
        logger_src = Path(__file__).with_name("litellm_logger.py")
        shutil.copy(logger_src, self._config_dir / "litellm_logger.py")

        self._config_path = config_path
        return config_path

    # ---- lifecycle ----

    def _resolve_port(self) -> int:
        if self._requested_port is None:
            port = find_free_ports(start_port=8000, count=1)[0]
            if self._logger:
                self._logger.debug(
                    f"No port requested; dynamically found free port: {port}"
                )
            return port

        if is_port_in_use(self._requested_port, self._host):
            if self._force_port:
                if self._logger:
                    self._logger.error(
                        f"Requested port {self._requested_port} is in use and force_port=True."
                    )
                raise OSError(
                    f"Port {self._requested_port} is already in use and force_port=True."
                )
            port = find_free_ports(start_port=self._requested_port, count=1)[0]
            if self._logger:
                self._logger.warning(
                    f"Requested port {self._requested_port} is already in use. "
                    f"Falling back to next available port: {port}"
                )
            return port

        if self._logger:
            self._logger.debug(f"Requested port {self._requested_port} is available.")
        return self._requested_port

    def serve(self) -> None:
        if self._logger:
            self._logger.info("Starting the LiteLLM proxy server...")

        if self._process and self._process.poll() is None:
            if self._logger:
                self._logger.warning(
                    "Attempted to start proxy, but a process is already running. Ignoring."
                )
            return

        self.port = self._resolve_port()
        config_path = self._write_config()

        env = os.environ.copy()
        env["PROXY_TRACE_LOG_PATH"] = str(self._metadata_log_path)

        assert self._config_dir is not None
        log_path = self._config_dir / "proxy.log"
        self._log_fp = open(log_path, "a", buffering=1)

        cmd = [
            "litellm",
            "--config",
            str(config_path),
            "--host",
            self._host,
            "--port",
            str(self.port),
            "--num_workers",
            "1",
            "--telemetry",
            "False",
        ]

        self._process = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(self._config_dir),
            stdout=self._log_fp,
            stderr=self._log_fp,
            close_fds=True,
        )

        if self._logger:
            self._logger.info(
                f"Subprocess spawned with PID: {self._process.pid}. Waiting for port {self.port} to open..."
            )

        # Wait for proxy to be ready
        deadline = time() + 30
        while not is_port_in_use(self.port, self._host):
            if time() > deadline:
                self.stop()
                if self._logger:
                    self._logger.error(
                        f"LiteLLM proxy startup timed out after 30s on {self._host}:{self.port}"
                    )
                raise TimeoutError(
                    f"LiteLLM proxy did not start within 30s on {self._host}:{self.port}"
                )
            if self._process.poll() is not None:
                self.stop()
                if self._logger:
                    self._logger.error(
                        f"LiteLLM proxy crashed unexpectedly during startup. Exit code: {self._process.returncode}"
                    )
                raise RuntimeError(
                    f"LiteLLM proxy exited with code {self._process.returncode}"
                )
            sleep(0.5)

        if self._logger:
            self._logger.info(
                f"LiteLLM proxy successfully started and listening on http://{self._host}:{self.port}"
            )

    def stop(self) -> None:
        if self._logger:
            self._logger.info("Stopping LiteLLM proxy server...")

        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if self._logger:
                        self._logger.warning(
                            "Process did not terminate within 10s. Sending SIGKILL."
                        )
                    self._process.kill()
                    self._process.wait(timeout=5)
                    if self._logger:
                        self._logger.debug("Process forcefully killed.")
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        f"Exception encountered while stopping process: {e}"
                    )
            finally:
                self._process = None

        if self._log_fp:
            try:
                self._log_fp.close()
            except Exception:
                pass
            self._log_fp = None

        # Clean up temp config dir
        if self._config_dir and self._config_dir.exists():
            if (self._config_dir / "proxy.log").exists():
                with open(self._config_dir / "proxy.log", "r") as f:
                    proxy_logs = f.read()
                if self._logger:
                    self._logger.info(f"Proxy server logs:\n\n{proxy_logs}")

            try:
                shutil.rmtree(self._config_dir)
            except OSError:
                pass
            self._config_dir = None
            self._config_path = None

        if self._logger:
            self._logger.info("LiteLLM proxy fully stopped.")

    # ---- query ----

    def get_base_url(self) -> str:
        if self.port is None:
            if self._logger:
                self._logger.error(
                    "get_base_url() called but the proxy is not running (port is None)."
                )
            raise RuntimeError("Proxy has not been started yet; call serve() first.")
        return f"http://{self._host}:{self.port}"

    def load_traces(self) -> list[dict]:
        return MetadataLogger.load_log(self._metadata_log_path)

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # ---- context manager ----

    def __enter__(self):
        self.serve()
        return self

    def __exit__(self, *exc):
        self.stop()

    def __del__(self):
        self.stop()
