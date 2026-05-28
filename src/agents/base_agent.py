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

from abc import ABC, abstractmethod
from pathlib import Path

from src.utils.judge import Judge
from src.utils.logger import Event, LogLevel


class BaseAgent(ABC):
    """
    A very simple interface for all agents that we want to
    use and test in this repo.
    """

    @abstractmethod
    def run(
        self,
        initial_instruction: str,
        log_path: Path | None = None,
        metadata_log_path: Path | None = None,
        logging_level: LogLevel | int = "DEBUG",
        *args,
        **kwargs,
    ) -> None:
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
        check_for_action: str | None = None,
        refusal_judge: Judge | None = None,
        specific_initial_instruction: str | None = None,
    ) -> dict[str, int | float | bool]:
        """
        Should return the corresponding metrics and a boolean
        flag indicating if the metrics were possible to be
        calculated in their entirety or not.
        """
        pass
