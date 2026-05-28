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

import hashlib
from abc import ABC, abstractmethod
from logging import FileHandler, Logger
from pathlib import Path

from docker.models.containers import Container

from src.benchmark_apps.base_benchmark_app import BenchmarkApp


class BaseContainerCallback(ABC):

    HASH_MARKER_PREFIX = "CALLBACK_POSITIVE_HASH"

    def __init__(
        self, benchmark_app: BenchmarkApp, use_additional_description: bool = True
    ) -> None:
        self._benchmark_app = benchmark_app
        self._use_additional_description = use_additional_description

    @staticmethod
    def _load_logfile_from_logger(logger: Logger) -> str | None:
        """
        For correctness, it assumes that the logger has only one FileHandler attached.
        This is true for our repository.
        """
        for handler in logger.handlers:
            if isinstance(handler, FileHandler):
                logfile_path = Path(handler.baseFilename)
                with open(
                    logfile_path, "r", encoding="utf-8", errors="replace"
                ) as logfile:
                    return logfile.read()
        return None

    @staticmethod
    def hash_logfile(logfile_content: str) -> str:
        first_line = logfile_content.splitlines()[0] if logfile_content else ""
        return hashlib.sha256(first_line.encode("utf-8")).hexdigest()

    @classmethod
    def has_positive_hash(cls, logfile_content: str) -> bool:
        marker = f"{cls.HASH_MARKER_PREFIX} {cls.hash_logfile(logfile_content)}"
        return marker in logfile_content

    @classmethod
    def report_positive_hash(cls, logger: Logger) -> None:
        logfile_content = cls._load_logfile_from_logger(logger)
        if logfile_content is None:
            return None

        logger.info(f"{cls.HASH_MARKER_PREFIX} {cls.hash_logfile(logfile_content)}")

    def _with_additional_description(self, prompt: str) -> str:
        if not self._use_additional_description:
            return prompt
        if self._benchmark_app.additional_description.strip():
            return (
                f"{prompt.rstrip()}\n\n"
                f"Additional information on the application:\n"
                f"{self._benchmark_app.additional_description.strip()}"
            )
        return prompt

    @abstractmethod
    def on_setup(
        self,
        container: Container,
        front_port: int,
        logger: Logger,
    ) -> None:
        return None

    @abstractmethod
    def on_teardown(
        self,
        container: Container,
        front_port: int,
        logger: Logger,
    ) -> None:
        pass

    @abstractmethod
    def get_callback_prompt(self) -> str:
        pass
