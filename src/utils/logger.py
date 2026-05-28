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

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Literal, Union

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type Event = dict[str, Any]


class MetadataLogger:
    """
    A class to provider a reusable interface for writing custom json event logs.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()

    @staticmethod
    def load_log(path) -> list[Event]:
        """
        Static utility function to load metadata logs. Static, as we want
        to separate code that only reads metadata logfiles from code that writes.
        Sorts by time_in if this key exists in the events.
        """
        try:
            loaded_log: list[Event] = []
            with open(path, "r") as f:
                for line in f:
                    if line.strip():
                        loaded_log.append(json.loads(line))

            # Sort by time_in if the key exists in any event
            if loaded_log and "time_in" in loaded_log[0]:
                loaded_log.sort(key=lambda event: event.get("time_in", float("inf")))

            return loaded_log
        except FileNotFoundError:
            raise FileNotFoundError(
                f"The referenced logfile could not be found on the path: {path}"
            )
        except Exception as e:
            raise e

    def log(self, event: Event) -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")


def get_datetime() -> str:
    """
    Generates a timestamp string suitable for log filenames.

    Returns:
        str: A string representing the current date and time in the format YYYYMMDD_HHMMSS.
    """
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return timestamp


def setup_meta_logger(meta_logfile_path: Path) -> MetadataLogger:
    """
    A painfully simple constructor wrapper for the meta logger to unify the usage with
    the classical text logger.

    Args:
        meta_logfile_path (str): Path to which the metadata logger should write.

    Returns:
        MetadataLogger: A configured metadata logger.
    """
    return MetadataLogger(path=meta_logfile_path)


def setup_logger(
    logger_name: str, logfile_path: Path, logging_level: Union[int, LogLevel]
) -> logging.Logger:
    """
    Creates a logger that can be used. Note that if you wish to close this logger
    before the program terminates, you will have to do that manually.

    Args:
        logger_name (str): Name of the logger. Make sure that you use unique
            names across loggers.
        logfile_path (pathlib.Path): Path under which the logfile will be saved.
        logging_level (int or LogLevel): The severity levels of the logs to save.

    Returns:
        logging.Logger: The configured logger.
    """

    logger = logging.getLogger(logger_name)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging_level)

    logfile_path.parent.mkdir(parents=True, exist_ok=True)

    logfile_handler = logging.FileHandler(logfile_path, mode="a")
    logfile_handler.setLevel(logging_level)

    formatter = logging.Formatter(fmt="%(levelname)s %(asctime)s\n%(message)s")
    logfile_handler.setFormatter(formatter)

    logger.addHandler(logfile_handler)

    return logger


def close_logger(logger: logging.Logger) -> None:
    """
    Closes all handlers associated with a logger and removes them.

    Args:
        logger (logging.Logger): The logger to close.
    """
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
