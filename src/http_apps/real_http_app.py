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
import os
import secrets
import shutil
import tempfile
from logging import Logger
from pathlib import Path
from typing import Generator

import docker
from docker.models.containers import Container

from src.benchmark_apps.base_benchmark_app import BenchmarkApp, RealApp
from src.callbacks import BaseContainerCallback
from src.http_apps.base_http_app import BaseHttpApp, ConnectionMonitor
from src.utils.constants import FASTAPI_BAXBENCH_DOCKERFILE
from src.utils.docker_utils import build_image_if_needed
from src.utils.judge import Judge
from src.utils.logger import Event, LogLevel, setup_logger


class RealHttpApp(BaseHttpApp):

    def __init__(self) -> None:
        super().__init__()

        # fixed internal state
        self._client: docker.DockerClient = docker.from_env()

        # resettable internal state
        self._container: Container | None
        self._temp_app_dir: Path | None
        self._real_app: RealApp | None
        self._reset_internal_state()

    def _identify_real_app(self, benchmark_app: BenchmarkApp, tag: str) -> RealApp:
        matching_real_apps = [ra for ra in benchmark_app.real_apps if ra.tag == tag]
        if len(matching_real_apps) != 1:
            options = [ra.tag for ra in benchmark_app.real_apps]
            raise ValueError(
                f"{len(matching_real_apps)} matching real apps found for the tag {tag}, but required is exactly 1. Options for this benchmark app are: {options}"
            )
        else:
            return matching_real_apps[0]

    def _reset_internal_state(
        self, benchmark_app: BenchmarkApp | None = None, tag: str = "sec"
    ) -> None:
        self._container = None
        self._temp_app_dir = None
        if benchmark_app is not None:
            self._real_app = self._identify_real_app(
                benchmark_app=benchmark_app, tag=tag
            )
        else:
            self._real_app = None

    def _cleanup_temp(self) -> None:
        if self._temp_app_dir is not None and self._temp_app_dir.exists():
            shutil.rmtree(self._temp_app_dir)
        self._temp_app_dir = None

    def _launch_front(
        self,
        benchmark_app: BenchmarkApp,
        tag: str,
        front_port: int,
        logger: Logger,
        connection_monitor: ConnectionMonitor,
        container_callback: BaseContainerCallback | None = None,
    ) -> None:
        build_image_if_needed(
            dockerfile=FASTAPI_BAXBENCH_DOCKERFILE[0],
            tag=FASTAPI_BAXBENCH_DOCKERFILE[1],
            logger=logger,
        )

        self._temp_app_dir = Path(tempfile.mkdtemp(prefix="http-realapp-"))

        if self._real_app is None:
            raise ValueError(
                "No real app found. The real app has to be set before launching."
            )
        os.system(f"cp {str(self._real_app.code_path)} {str(self._temp_app_dir)}")

        entry_cmd = ["python3", "app.py"]

        try:
            logger.info("Starting the container.")
            self._container = self._client.containers.run(
                image=FASTAPI_BAXBENCH_DOCKERFILE[1],
                command=entry_cmd,
                detach=True,
                name=f"http-webapp-{benchmark_app.name}-{tag}-{front_port}",
                ports={"5000/tcp": front_port},
                volumes={str(self._temp_app_dir): {"bind": "/app"}},
                working_dir="/app",
            )
            connection_monitor.wait_until_online(
                url=f"http://localhost:{front_port}", timeout=30, logger=logger
            )
            logger.info(
                f"Container started successfully. The webapp will be accessible at http://localhost:{front_port}"
            )

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
                logger.error(
                    f"Container logs of the front-app:\n{container_logs.decode('utf-8')}"
                )
            self._cleanup_temp()
            raise e
        except Exception as e:
            logger.error(f"An unexpected error occurred:\n{e}")
            if self._container is not None:
                self._container.reload()
                container_logs = self._container.logs(
                    stdout=True, stderr=True, follow=False
                )
                logger.error(
                    f"Container logs of the front-app:\n{container_logs.decode('utf-8')}"
                )
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

                logger.info(
                    f"Container logs of the front-app:\n{container_logs.decode('utf-8')}"
                )
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
        backend_port: int = 8001,  # unused in this class, only API
        container_callback: BaseContainerCallback | None = None,
        log_path: Path | None = None,
        metadata_log_path: Path | None = None,  # unused in this class, only API
        logging_level: LogLevel | int = "DEBUG",
    ) -> Generator:

        if log_path is None:
            raise ValueError("'log_path' has to be an instance of Path and not None.")

        with contextlib.ExitStack() as stack:

            logger = setup_logger(
                logger_name=f"http-webapp-{benchmark_app.name}-{tag}-{front_port}-{secrets.token_urlsafe(10)}",
                logfile_path=log_path,
                logging_level=logging_level,
            )

            front_connection_monitor = ConnectionMonitor("front")

            self._reset_internal_state(benchmark_app=benchmark_app, tag=tag)

            self._launch_front(
                benchmark_app=benchmark_app,
                tag=tag,
                front_port=front_port,
                logger=logger,
                connection_monitor=front_connection_monitor,
                container_callback=container_callback,
            )

            # prepare the teardown stack for exit
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

    def can_calculate_metrics(
        self, log_path: Path | None = None, metadata_log_path: Path | None = None
    ) -> bool:
        return True

    def calculate_metrics(
        self,
        log_path: Path | None = None,
        metadata_log_path: Path | None = None,
        secrets: list[str] | None = None,
        custom_costs: dict[str, float] | None = None,
        prompt_injection_judge: Judge | None = None,
    ) -> dict[str, int | float | bool]:
        all_metrics: dict[str, int | float | bool] = {"complete": True}
        return all_metrics
