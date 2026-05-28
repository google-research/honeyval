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

import json
import secrets
from logging import Logger
from pathlib import Path
from typing import Callable, cast

import numpy as np

from src.agents import BaseAgent
from src.benchmark_apps import BenchmarkApp
from src.benchmark_prompts import AgentPrompt
from src.callbacks import CallbackConfig
from src.http_apps import BaseHttpApp, HttpLLMHoneypot
from src.tasks.base_task import Subtask
from src.utils.judge import Judge
from src.utils.logger import MetadataLogger, setup_logger
from src.utils.port_finder import wait_until_port_is_free


class StaticVsHttpApp(Subtask):
    """
    Benchmark task for testing (honeypot) http applications against
    the static test suite of the emulated application.
    """

    name = "static-vs-http-app"
    n_ports = 2
    uses_agent = False

    def __init__(
        self,
        benchmark_app: BenchmarkApp,
        http_app: BaseHttpApp,
        agent: BaseAgent,
        agent_initial_instruction: AgentPrompt,
        base_path: Path,
        real_app_tag: str = "sec",
        callback_config: CallbackConfig | None = None,
        secrets: list[str] | None = None,
        check_for_action: str | None = None,
        custom_costs: dict[str, float] | None = None,
        prompt_injection_judge: Judge | None = None,
        refusal_judge: Judge | None = None,
        sample: int = -1,
    ) -> None:
        super().__init__(
            benchmark_app=benchmark_app,
            http_app=http_app,
            agent=agent,
            agent_initial_instruction=agent_initial_instruction,
            base_path=base_path,
            real_app_tag=real_app_tag,
            secrets=secrets,
            callback_config=callback_config,
            check_for_action=check_for_action,
            custom_costs=custom_costs,
            prompt_injection_judge=prompt_injection_judge,
            refusal_judge=refusal_judge,
            sample=sample,
        )

    def run(self, front_port: int, backend_port: int, proxy_port: int) -> None:

        n_tests = len(self.benchmark_app.functional_tests)

        self._subtask_logger = self._get_subtask_logger()
        self._subtask_logger.info(
            f"Starting the task. Number of tests to run: {n_tests}."
        )
        self._log_task_secrets()

        ft_results = {"ft_total": n_tests, "ft_pass": 0}
        n_errors = 0
        for ft in self.benchmark_app.functional_tests:
            ft_name = cast(Callable[[int, Logger], bool], ft).__name__
            test_logger = setup_logger(
                logger_name=(
                    f"{self.name}-tests-{self.benchmark_app.name}"
                    f"-{self.sample}-{ft_name}-{secrets.token_urlsafe(10)}"
                ),
                logfile_path=self._subtask_save_path
                / "logs"
                / f"ft_tests_{ft_name}.log",
                logging_level="INFO",
            )
            self._subtask_logger.info(f"Running test: {ft_name}.")
            try:

                with self.http_app.launch(
                    benchmark_app=self.benchmark_app,
                    tag=self.real_app_tag,
                    front_port=front_port,
                    backend_port=backend_port,
                    log_path=self._subtask_save_path
                    / "logs"
                    / f"http-app-{ft_name}.log",
                    metadata_log_path=self._subtask_save_path
                    / "metadata-logs"
                    / f"http-app-metadata-{ft_name}.jsonl",
                ):

                    try:
                        correct = ft(front_port, test_logger)
                    except Exception as e:
                        correct = False
                        test_logger.error(
                            f"An exception occurred while trying to execute the test:\n{e}"
                        )
                    ft_results["ft_pass"] += 1 if correct else 0

                self._subtask_logger.info(
                    f"Execution of {ft_name} finished. Waiting to free the port."
                )
                wait_until_port_is_free(port=front_port)
                wait_until_port_is_free(port=backend_port)
                self._subtask_logger.info(f"Ports freed.")
            except Exception as e:
                self._subtask_logger.warning(
                    f"An error occurred while executing {ft_name}:\n{e}"
                )
                n_errors += 1
                continue

        with open(self._subtask_save_path / "test_result.json", "w") as f:
            json.dump(ft_results, f)

        self._subtask_logger.info(f"Task finished. Number of errors: {n_errors}")

    def can_calculate_metrics(self) -> bool:

        can_calc_all: list[bool] = []
        # check if all the http-app metrics can be computed for each test
        for ft in self.benchmark_app.functional_tests:
            ft_name = cast(Callable[[int, Logger], bool], ft).__name__
            metadata_log_path = (
                self._subtask_save_path
                / "metadata-logs"
                / f"http-app-metadata-{ft_name}.jsonl"
            )
            can_calc = self.http_app.can_calculate_metrics(
                log_path=self._subtask_save_path / "logs" / f"http-app-{ft_name}.log",
                metadata_log_path=metadata_log_path,
            )
            can_calc_all.append(can_calc)

            if isinstance(self.http_app, HttpLLMHoneypot):
                try:
                    metadata = MetadataLogger.load_log(metadata_log_path)
                    has_command = any(event["event"] == "COMMAND" for event in metadata)
                    can_calc_all.append(has_command)
                except Exception:
                    can_calc_all.append(False)

        # check if the test results exist
        test_results_path = self._subtask_save_path / "test_result.json"
        can_calc_all.append(test_results_path.is_file())

        # check if the entire task ran without errors
        subtask_log_path = self._subtask_save_path / "task.log"
        subtask_ok = False
        if subtask_log_path.is_file():
            with open(subtask_log_path, "r") as f:
                subtask_log = f.read()
            subtask_ok = "Task finished. Number of errors: 0" in subtask_log
        can_calc_all.append(subtask_ok)

        return all(can_calc_all)

    def calculate_metrics(self, front_port: int = 8000) -> None:
        if not hasattr(self, "_subtask_logger"):
            self._subtask_logger = self._get_subtask_logger()

        self._subtask_logger.info(f"Calculating the metrics.")

        self._subtask_logger.info(f"Http-app-only metrics.")

        for ft in self.benchmark_app.functional_tests:
            try:
                ft_name = cast(Callable[[int, Logger], bool], ft).__name__
                http_app_metrics = self.http_app.calculate_metrics(
                    log_path=self._subtask_save_path
                    / "logs"
                    / f"http-app-{ft_name}.log",
                    metadata_log_path=self._subtask_save_path
                    / "metadata-logs"
                    / f"http-app-metadata-{ft_name}.jsonl",
                    secrets=None,
                    prompt_injection_judge=self.prompt_injection_judge,
                    custom_costs=None,
                )

                with open(
                    self._subtask_save_path / f"http-app-metrics-{ft_name}.json", "w"
                ) as f:
                    json.dump(http_app_metrics, f, indent=4)

                self._subtask_logger.info(
                    f"Successfully saved the http-app-only metrics for the test {ft_name}. Complete: {http_app_metrics['complete']}"
                )
            except Exception as e:
                self._subtask_logger.warning(
                    f"Could not calculate and save the http-only-metric for the functional test: {ft_name}:\n{e}"
                )
                with open(
                    self._subtask_save_path / f"http-app-metrics-{ft_name}.json", "w"
                ) as f:
                    json.dump({"complete": False}, f, indent=4)

    def load_and_process_metrics(self) -> dict[str, int | float | bool]:

        processed_metrics: dict[str, int | float | bool] = {}

        try:
            ft_metrics = []
            for ft in self.benchmark_app.functional_tests:
                ft_name = cast(Callable[[int, Logger], bool], ft).__name__
                metric_path = (
                    self._subtask_save_path / f"http-app-metrics-{ft_name}.json"
                )
                with open(metric_path, "r") as f:
                    metrics = json.load(f)
                ft_metrics.append(metrics)

            test_results_path = self._subtask_save_path / "test_result.json"
            with open(test_results_path, "r") as f:
                test_results = json.load(f)

            processed_metrics["ft_pass"] = (
                test_results["ft_pass"] == test_results["ft_total"]
                and test_results["ft_total"] > 0
            )

            # pool the ft metrics
            for metric in ft_metrics[0].keys():
                if not metric.startswith("total") and not metric.startswith(
                    "n_prompt_injection"
                ):
                    continue
                processed_metrics[metric] = sum(ftm[metric] for ftm in ft_metrics)

            processed_metrics["mean_response_time"] = (
                processed_metrics["total_interaction_time"]
                / processed_metrics["total_interaction_rounds"]
            )
            processed_metrics["median_response_time"] = float(
                np.mean([ftm["median_response_time"] for ftm in ft_metrics])
            )
            processed_metrics["min_response_time"] = min(
                ftm["min_response_time"] for ftm in ft_metrics
            )
            processed_metrics["max_response_time"] = max(
                ftm["max_response_time"] for ftm in ft_metrics
            )
            processed_metrics["final_in"] = np.mean(
                [ftm["final_in"] for ftm in ft_metrics]
            )

            return processed_metrics

        except Exception as e:
            raise e
