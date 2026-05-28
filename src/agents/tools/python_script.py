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

from src.agents.tools.base_tool import BaseTool
from src.sandkasten import DockerSandkasten

PYTHON_SCRIPT_DESCRIPTION = """
This tool allows you to write and execute a Python script inside a secure sandbox environment.

INPUT FORMAT:
Your input must be a complete, valid Python script as a plain string. The script is written to a
temporary file inside a tool sandbox and executed with the system Python 3 interpreter.

CONSTRAINTS:
- Only requests and the Python standard library modules are available. You CANNOT import third-party packages (e.g. numpy, pandas).
- The script runs with a timeout. Long-running or blocking scripts will be killed.
- The script is executed in a tool sandbox and network access depends on the sandbox configuration.

OUTPUT:
- On success: everything the script writes to stdout is returned.
- On failure (non-zero exit code): the stderr output is returned so you can diagnose errors.
"""


class PythonScriptTool(BaseTool):

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        super().__init__()

    def _set_name_and_desc(self) -> None:
        self.name = "python_script"
        self.description = PYTHON_SCRIPT_DESCRIPTION

    def __call__(self, tool_input: str, sandbox: DockerSandkasten) -> str:

        try:
            container = sandbox.container
            if container is None:
                raise ValueError("Sandbox container is not available.")
            script_path = "/tmp/_agent_script.py"

            import io
            import tarfile

            script_bytes = tool_input.encode("utf-8")
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                info = tarfile.TarInfo(name="_agent_script.py")
                info.size = len(script_bytes)
                tar.addfile(info, io.BytesIO(script_bytes))
            tar_stream.seek(0)
            container.put_archive("/tmp", tar_stream)

            exit_code, (stdout, stderr) = container.exec_run(
                ["timeout", f"{self.timeout}s", "python3", script_path],
                demux=True,
            )

            if exit_code != 0:
                err = stderr.decode("utf-8") if stderr else ""
                out = stdout.decode("utf-8") if stdout else ""
                return (out + err).strip() or f"Script exited with code {exit_code}."
            else:
                return stdout.decode("utf-8") if stdout else ""

        except Exception as e:
            return f"Script execution failed due to a tool error: {str(e)}"
