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

import shlex
import subprocess

from src.agents.tools.base_tool import BaseTool
from src.sandkasten import DockerSandkasten

YOLO_BASH_DESCRIPTION = """
This tool gives you access to a terminal to execute arbitrary bash commands. Your input to this tool should be simply a valid bash command that you want to execute and nothing else.
"""


class YoloBashTool(BaseTool):

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        super().__init__()

    def _set_name_and_desc(self) -> None:
        self.name = "bash"
        self.description = YOLO_BASH_DESCRIPTION

    def __call__(self, tool_input: str, sandbox: DockerSandkasten) -> str:

        try:
            container = sandbox.container
            if container is None:
                raise ValueError("Sandbox container is not available.")
            exit_code, (stdout, stderr) = container.exec_run(
                ["timeout", f"{self.timeout}s", "bash", "-c", tool_input], demux=True
            )

            if exit_code != 0:
                return stderr.decode("utf-8")
            else:
                return stdout.decode("utf-8")

        except Exception as e:
            return str(e)
