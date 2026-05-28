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

from src.agents.tools.base_tool import BaseTool
from src.sandkasten import DockerSandkasten
from src.utils.cmd_parsing import sanitize_curl

UNRESTRICTED_CURL_DESCRIPTION = """
This tool gives you access to the `curl` command. Your input to this tool should be a single valid curl command as if you were typing it into a shell, e.g., `curl http://address.com`. You have to include the "curl" command in the beginning of your input as well.
"""

RESTRICTED_CURL_DESCRIPTION = """
This tool gives you access to a secure and restricted version of the `curl` command. Your input to this tool should be a single valid curl command as if you were typing it into a shell, e.g., `curl http://address.com`. You have to include the "curl" command in the beginning of your input as well. The tool supports all fields, arguments, and syntax of the usual curl command, however, the target url of your command will always be sanitized and replaced with {restricted_url}. For instance, the above example input would be turned into `curl {restricted_url}`.
"""


class CurlTool(BaseTool):

    def __init__(self, timeout: int = 30, restrict_to_url: str | None = None):
        self.restrict_to_url = restrict_to_url
        self.timeout = timeout
        super().__init__()

    def _set_name_and_desc(self) -> None:
        self.name = "curl"
        if self.restrict_to_url:
            self.description = RESTRICTED_CURL_DESCRIPTION.format(
                restricted_url=self.restrict_to_url
            )
        else:
            self.description = UNRESTRICTED_CURL_DESCRIPTION

    def change_restriction(self, new_restrict_to_url: str | None) -> None:
        self.restrict_to_url = new_restrict_to_url
        self._set_name_and_desc()

    def __call__(self, tool_input: str, sandbox: DockerSandkasten) -> str:

        try:
            container = sandbox.container
            if container is None:
                raise ValueError("Sandbox container is not available.")
            sanitized_command = sanitize_curl(
                cmd=tool_input, restrict_to_url=self.restrict_to_url
            )

            exit_code, (stdout, stderr) = container.exec_run(
                [
                    "timeout",
                    f"{self.timeout}s",
                    "bash",
                    "-c",
                    shlex.join(sanitized_command),
                ],
                demux=True,
            )
            if exit_code != 0:
                return stderr.decode("utf-8")
            else:
                if stdout is None:
                    return ""
                else:
                    return stdout.decode("utf-8")

        except Exception as e:
            return f"Request failed due to tool call error: {str(e)}"
