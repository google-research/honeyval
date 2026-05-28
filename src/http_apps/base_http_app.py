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
from abc import ABC, abstractmethod
from logging import Logger
from pathlib import Path
from time import sleep, time
from typing import Generator

import requests

from src.benchmark_apps import BenchmarkApp
from src.callbacks import BaseContainerCallback
from src.utils.judge import Judge
from src.utils.logger import Event, LogLevel


class ConnectionMonitor:

    def __init__(self, name: str) -> None:
        self._name = name

    def check_online(self, url: str, logger: Logger | None = None) -> bool:
        try:
            requests.get(url)
            if logger is not None:
                logger.info(f"The {self._name} server is up!")
            return True
        except requests.ConnectionError as e:
            if logger is not None:
                logger.warning(f"The {self._name} server is not up: {e}")
            return False

    def wait_until_online(
        self, url: str, timeout: int = 30, logger: Logger | None = None
    ) -> None:
        start = time()
        while not self.check_online(url, logger):
            if time() - start > timeout:
                raise TimeoutError(f"Unable to start the {self._name} server on time.")
            sleep(1.0)

    def wait_until_offline(
        self, url: str, timeout: int = 30, logger: Logger | None = None
    ) -> None:
        start = time()
        while self.check_online(url, logger):
            if time() - start > timeout:
                raise TimeoutError(
                    f"Unable to stop the {self._name} server on time. Perhaps you need to stop it manually."
                )
            sleep(1.0)


class BaseHttpApp(ABC):

    @abstractmethod
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
        pass

    @abstractmethod
    def can_calculate_metrics(
        self, log_path: Path | None = None, metadata_log_path: Path | None = None
    ) -> bool:
        pass

    @abstractmethod
    def calculate_metrics(
        self,
        log_path: Path | None = None,
        metadata_log_path: Path | None = None,
        secrets: list[str] | None = None,
        custom_costs: dict[str, float] | None = None,
        prompt_injection_judge: Judge | None = None,
    ) -> dict[str, int | float | bool]:
        """
        This method should return the corresponding aggregatable
        metrics and a boolean flag indicating if the metrics
        could be calculated to completion, without missing data
        or experiments.
        """
        pass
