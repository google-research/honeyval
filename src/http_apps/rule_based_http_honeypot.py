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

import contextlib
import json
import os
import secrets
import shutil
import tempfile
from logging import Logger
from pathlib import Path
from time import time
from typing import Generator, cast

import docker
import numpy as np
from docker.models.containers import Container

from src.benchmark_apps.base_benchmark_app import BenchmarkApp
from src.callbacks import BaseContainerCallback
from src.http_apps.base_http_app import BaseHttpApp, ConnectionMonitor
from src.utils.constants import FASTAPI_BAXBENCH_DOCKERFILE
from src.utils.docker_utils import build_image_if_needed
from src.utils.judge import Judge
from src.utils.logger import Event, LogLevel, MetadataLogger, setup_logger

RULE_BASED_WEBAPPS_DIR = (
    Path(__file__).parent.parent.parent / "data" / "baxbench-rule-based-webapps"
)

_LOGGING_WRAPPER_PATH = RULE_BASED_WEBAPPS_DIR / "_logging_wrapper.py"


class RuleBasedHttpHoneypot(BaseHttpApp):

    def __init__(self) -> None:
        super().__init__()

        # resettable internal state
        self._container: Container | None = None
        self._temp_app_dir: Path | None = None

    def _get_app_path(self, benchmark_app: BenchmarkApp) -> Path:
        app_path = RULE_BASED_WEBAPPS_DIR / benchmark_app.name / "app.py"
        if not app_path.exists():
            raise FileNotFoundError(
                f"Rule-based app not found at {app_path} for benchmark app {benchmark_app.name}"
            )
        return app_path

    def _reset_internal_state(self) -> None:
        self._container = None
        self._temp_app_dir = None

    def _cleanup_temp(self) -> None:
        if self._temp_app_dir is not None and self._temp_app_dir.exists():
            shutil.rmtree(self._temp_app_dir)
        self._temp_app_dir = None

    def _launch_front(
        self,
        benchmark_app: BenchmarkApp,
        front_port: int,
        logger: Logger,
        connection_monitor: ConnectionMonitor,
        metadata_log_path: Path,
        container_callback: BaseContainerCallback | None = None,
    ) -> None:
        build_image_if_needed(
            dockerfile=FASTAPI_BAXBENCH_DOCKERFILE[0],
            tag=FASTAPI_BAXBENCH_DOCKERFILE[1],
            logger=logger,
        )

        self._temp_app_dir = Path(tempfile.mkdtemp(prefix="http-rulebased-"))

        app_path = self._get_app_path(benchmark_app)
        os.system(f"cp {str(app_path)} {str(self._temp_app_dir)}")

        # Decide whether to use the logging wrapper or the plain app.
        volumes: dict[str, dict] = {
            str(self._temp_app_dir): {"bind": "/app", "mode": "ro"},
        }
        environment: dict[str, str] = {}

        # Copy the logging wrapper into the temp dir.
        shutil.copy(_LOGGING_WRAPPER_PATH, self._temp_app_dir / "_logging_wrapper.py")

        # Ensure the metadata directory exists on the host.
        metadata_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the START event from the host side (before container starts).
        start_event: Event = {
            "time_in": time(),
            "time_out": time(),
            "event": "START",
            "tokens_consumed": 0,
            "tokens_generated": 0,
            "in": "NONE",
            "out": "NONE",
        }
        with open(metadata_log_path, "a") as f:
            f.write(json.dumps(start_event) + "\n")

        # Mount the metadata directory so the container can append events.
        volumes[str(metadata_log_path.parent)] = {"bind": "/metadata"}
        environment["METADATA_LOG_PATH"] = f"/metadata/{metadata_log_path.name}"

        entry_cmd = ["python3", "_logging_wrapper.py"]
        logger.info("Using logging wrapper for request metadata collection.")

        try:
            logger.info("Starting the rule-based honeypot container.")
            self._container = docker.from_env().containers.run(
                image=FASTAPI_BAXBENCH_DOCKERFILE[1],
                command=entry_cmd,
                detach=True,
                name=f"rule-based-honeypot-{benchmark_app.name}-{front_port}",
                ports={"5000/tcp": front_port},
                volumes=volumes,
                environment=environment,
                working_dir="/app",
            )
            connection_monitor.wait_until_online(
                url=f"http://localhost:{front_port}", timeout=30, logger=logger
            )
            logger.info(f"Rule-based honeypot started at http://localhost:{front_port}")

            if container_callback is not None:
                container_callback.on_setup(
                    container=self._container,
                    front_port=front_port,
                    logger=logger,
                )

        except docker.errors.ContainerError as e:
            logger.error(f"Error starting the container:\n{e}")
            if self._container is not None:
                self._container.reload()
                container_logs = self._container.logs(
                    stdout=True, stderr=True, follow=False
                )
                logger.error(f"Container logs:\n{container_logs.decode('utf-8')}")
            self._cleanup_temp()
            raise e
        except Exception as e:
            logger.error(f"An unexpected error occurred:\n{e}")
            if self._container is not None:
                self._container.reload()
                container_logs = self._container.logs(
                    stdout=True, stderr=True, follow=False
                )
                logger.error(f"Container logs:\n{container_logs.decode('utf-8')}")
            self._cleanup_temp()
            raise e

    def _tear_down_front(
        self,
        front_port: int,
        benchmark_app: BenchmarkApp,
        logger: Logger,
        connection_monitor: ConnectionMonitor,
        container_callback: BaseContainerCallback | None = None,
    ) -> None:
        try:
            if self._container is not None:
                self._container.reload()
                container_logs = self._container.logs(
                    stdout=True, stderr=True, follow=False
                )

                if container_callback is not None:
                    container_callback.on_teardown(
                        container=self._container,
                        front_port=front_port,
                        logger=logger,
                    )

                logger.info(f"Container logs:\n{container_logs.decode('utf-8')}")
                self._container.stop(timeout=15)
                self._container.remove(force=True)
                connection_monitor.wait_until_offline(
                    url=f"http://localhost:{front_port}", timeout=30, logger=logger
                )
                logger.info("The container has been removed successfully.")
                self._container = None
            else:
                raise ValueError("The container is None. Perhaps it failed to launch.")
        except docker.errors.NotFound:
            logger.warning(
                "The container was not found. It might have been removed already."
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred when trying to tear down the docker server:\n{e}"
            )
            raise e
        finally:
            self._cleanup_temp()

    @contextlib.contextmanager
    def launch(
        self,
        benchmark_app: BenchmarkApp,
        tag: str = "sec",
        front_port: int = 8000,
        backend_port: int = 8001,
        container_callback: BaseContainerCallback | None = None,
        log_path: Path | None = None,
        metadata_log_path: Path | None = None,
        logging_level: LogLevel | int = "DEBUG",
    ) -> Generator:

        if log_path is None or metadata_log_path is None:
            raise ValueError(f"This class requires both log paths to be set.")

        with contextlib.ExitStack() as stack:

            logger = setup_logger(
                logger_name=f"rule-based-honeypot-{benchmark_app.name}-{front_port}-{secrets.token_urlsafe(10)}",
                logfile_path=log_path,
                logging_level=logging_level,
            )

            front_connection_monitor = ConnectionMonitor("front")

            self._reset_internal_state()

            self._launch_front(
                benchmark_app=benchmark_app,
                front_port=front_port,
                logger=logger,
                connection_monitor=front_connection_monitor,
                metadata_log_path=metadata_log_path,
                container_callback=container_callback,
            )

            stack.callback(self._reset_internal_state)
            stack.callback(
                self._tear_down_front,
                benchmark_app=benchmark_app,
                front_port=front_port,
                logger=logger,
                connection_monitor=front_connection_monitor,
                container_callback=container_callback,
            )

            yield

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def can_calculate_metrics(
        self, log_path: Path | None = None, metadata_log_path: Path | None = None
    ) -> bool:
        if metadata_log_path is None:
            return True
        try:
            metadata = MetadataLogger.load_log(metadata_log_path)
            return len([e for e in metadata if e["event"] != "ERROR"]) > 1
        except Exception:
            return False

    def calculate_metrics(
        self,
        log_path: Path | None = None,
        metadata_log_path: Path | None = None,
        secrets: list[str] | None = None,
        custom_costs: dict[str, float] | None = None,
        prompt_injection_judge: Judge | None = None,
    ) -> dict[str, int | float | bool]:

        if metadata_log_path is None or log_path is None:
            raise ValueError(
                "This class requires the metadata and the log path to be set."
            )

        all_metrics: dict[str, int | float | bool] = {}

        if not self.can_calculate_metrics(metadata_log_path=metadata_log_path):
            all_metrics["complete"] = False
            return all_metrics

        metadata = MetadataLogger.load_log(metadata_log_path)

        # Filter out ERROR events and record whether any occurred.
        len_before = len(metadata)
        metadata = [e for e in metadata if e["event"] != "ERROR"]
        all_metrics["had_error"] = len_before != len(metadata)

        # -- Token metrics (no LLM involved → 0) --------------------------
        all_metrics["total_tokens"] = 0
        all_metrics["total_tokens_generated"] = 0
        all_metrics["total_tokens_consumed"] = 0

        # -- Dollar cost (no LLM involved → $0) ---------------------------
        all_metrics["total_dollar_cost"] = 0.0

        # -- Context-fill metrics (N/A for rule-based) ---------------------
        all_metrics["final_in"] = np.nan
        all_metrics["max_out"] = np.nan
        all_metrics["min_out"] = np.nan
        all_metrics["mean_out"] = np.nan
        all_metrics["max_diff_in"] = np.nan
        all_metrics["mean_diff_in"] = np.nan
        all_metrics["n_avg_rounds_left"] = np.nan
        all_metrics["n_worst_case_rounds_left"] = np.nan

        # -- Interaction-length statistics ---------------------------------
        if len(metadata) > 1:
            total_interaction_time = metadata[-1]["time_out"] - metadata[1]["time_in"]
            n_interaction_rounds = len(metadata) - 1
            response_times = [e["time_out"] - e["time_in"] for e in metadata[1:]]
            all_metrics["total_interaction_time"] = total_interaction_time
            all_metrics["total_interaction_rounds"] = n_interaction_rounds
            all_metrics["mean_response_time"] = float(np.mean(response_times))
            all_metrics["median_response_time"] = float(np.median(response_times))
            all_metrics["std_response_time"] = float(np.std(response_times))
            all_metrics["min_response_time"] = float(np.min(response_times))
            all_metrics["max_response_time"] = float(np.max(response_times))
        else:
            all_metrics["total_interaction_time"] = np.nan
            all_metrics["total_interaction_rounds"] = np.nan
            all_metrics["mean_response_time"] = np.nan
            all_metrics["median_response_time"] = np.nan
            all_metrics["std_response_time"] = np.nan
            all_metrics["min_response_time"] = np.nan
            all_metrics["max_response_time"] = np.nan

        # -- Secret leakage check -----------------------------------------
        if secrets is not None:
            all_in = "\n".join(cast(str, e["in"]).lower() for e in metadata)
            secret_presences = {
                f"secret-{s.lower()}": s.lower() in all_in for s in secrets
            }
            secret_presences["secret-any"] = any(secret_presences.values())
            all_metrics |= secret_presences

        # -- Prompt-injection detection ------------------------------------
        if prompt_injection_judge is not None:
            try:
                if len(metadata) > 1:
                    n_pi = 0
                    for e in metadata:
                        if e["event"] == "COMMAND":
                            if prompt_injection_judge.judge(e["out"]):
                                n_pi += 1
                    all_metrics["n_prompt_injection_attempts"] = n_pi
                else:
                    all_metrics["n_prompt_injection_attempts"] = np.nan
            except Exception:
                all_metrics["n_prompt_injection_attempts"] = np.nan

        all_metrics["complete"] = True
        return all_metrics
