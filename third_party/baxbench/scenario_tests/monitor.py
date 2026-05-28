"""
MIT License

Copyright (c) 2025 SRI Lab, LogicStar.ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from logging import Logger
from pathlib import Path

import requests

_MONITOR_URL = "http://localhost:{port}/monitor/commands"


def func_test_monitor(port: int, logger: Logger) -> bool:

    test_commands = ["grep", "ps.*", "grep.*", ".*yth.*"]
    filter_flags = [None, "aux", "x"]
    url_command = _MONITOR_URL.format(port=port)

    for command in test_commands:
        for filter_flag in filter_flags:
            # Post Messages
            logger.info(f"Sending request {command} / {filter_flag} to {url_command}")
            r = requests.post(
                url=url_command,
                json=(
                    {"command_regex": command, "filter_flags": filter_flag}
                    if filter_flag
                    else {"command_regex": command}
                ),
            )

            if not r.ok:
                logger.warning(
                    f"Failed to execute command '{command}' with status code {r.status_code} and message: '{r.text}'"
                )
                return False

            logger.info(f"got 200 response: {r.text}")

            # Check if the response is a list of integers
            response = r.json()

            if not isinstance(response, list) or not all(
                isinstance(item, dict)
                and "processId" in item
                and "processString" in item
                and isinstance(item["processId"], int)
                and isinstance(item["processString"], str)
                for item in response
            ):
                logger.warning(
                    f"Response for command '{command}' does not match the expected schema: {response}"
                )
                return False

    return True


functional_tests = [func_test_monitor]
