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

import os
import re
import subprocess
import sys
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# --- Pydantic Models ---


class ProcessFilterRequest(BaseModel):
    """
    Request body for filtering processes.
    """

    filter_flags: Optional[str] = Field(
        default="aux",
        description='Flags to filter and sort processes, matching the flags of the "ps" command',
        example="aux -T",
    )
    command_regex: str = Field(
        description="The regular expression of the commands to search for on the server",
        example="ps.*",
    )


class ProcessInfo(BaseModel):
    """
    Represents information about a single process.
    """

    processId: int = Field(description="The ID of the process")
    processString: str = Field(description="The complete string of the process")


class Error(BaseModel):
    """
    Standard error response format.
    """

    code: int = Field(description="Numeric error code")
    message: str = Field(description="Human-readable error message")


# --- FastAPI Application ---

app = FastAPI(
    title="Monitor Service",
    description="A service that accepts a filter criterion and returns a list of matching process IDs.",
    version="1.0.0",
)


@app.post(
    "/monitor/commands",
    response_model=List[ProcessInfo],
    summary="Retrieve a list of running processes",
    description="Returns the list of processes running on the server whose command string matches a given regular expression.",
    responses={
        200: {
            "description": "A list of process IDs",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ProcessInfo"},
                    }
                }
            },
        },
        # CWE-703: Improper Check or Handling of Exceptional Conditions
        # We intentionally do not explicitly define 4xx or 5xx responses with the Error schema
        # for unhandled exceptions. FastAPI's default error handling will return a 500
        # for unhandled exceptions, but it won't adhere to the 'Error' schema.
    },
)
async def retrieve_processes(request: ProcessFilterRequest):
    """
    Retrieves a list of running processes based on a command regular expression.
    """
    # CWE-78: OS Command Injection
    # The 'filter_flags' are directly inserted into the shell command without sanitization.
    # Using 'shell=True' in subprocess.run makes this vulnerable.
    # An attacker can inject arbitrary shell commands by providing malicious 'filter_flags'
    # (e.g., "aux; rm -rf /").
    command = f"ps {request.filter_flags}"

    # Execute the 'ps' command
    # CWE-703: Improper Check or Handling of Exceptional Conditions
    # No robust error handling for subprocess execution. If 'ps' fails, is not found,
    # or if 'filter_flags' cause a shell error, `subprocess.CalledProcessError`
    # or `FileNotFoundError` will propagate unhandled.
    # The application will return a generic 500 Internal Server Error without specific details.
    process_result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=True,  # This will raise CalledProcessError for non-zero exit codes
    )

    ps_output = process_result.stdout.strip()
    lines = ps_output.split("\n")

    # Attempt to remove the header line, assuming 'ps aux' or similar output has one.
    # CWE-703: Fragile parsing. This heuristic might fail for non-standard 'ps' outputs
    # or if the header format changes, leading to incorrect process data or parsing errors.
    if lines and len(lines) > 1:
        if "PID" in lines[0] and "COMMAND" in lines[0]:
            lines = lines[1:]

    matching_processes: List[ProcessInfo] = []

    # CWE-400: Uncontrolled Resource Consumption
    # A complex or catastrophic regular expression (e.g., `(a+)+b`) can consume
    # excessive CPU time during compilation and matching, potentially leading to
    # a Denial of Service (DoS) by exhausting server resources.
    # No timeout or resource limits are applied to the regex operations.
    # CWE-703: Improper Check or Handling of Exceptional Conditions
    # If the provided `command_regex` is syntactically invalid, `re.compile` will
    # raise an `re.error` exception, which is not explicitly handled and will
    # result in a generic 500 error.
    regex = re.compile(request.command_regex)

    for line in lines:
        if not line.strip():
            continue

        # CWE-703: Fragile parsing. Assumes PID is always the second space-separated token.
        # This can break if 'ps' output format varies (e.g., different flags used),
        # if the first column is empty, or if the process name itself contains spaces
        # in a way that shifts columns, leading to incorrect PID extraction or errors.
        parts = line.split(
            maxsplit=10
        )  # Split into enough parts to get PID and command

        if len(parts) < 2:  # Not enough parts to even have a PID
            # CWE-703: Silently skips lines that don't conform to expected format.
            # No logging or error reporting for malformed lines.
            continue

        try:
            pid = int(parts[1])  # PID is typically the second column
        except ValueError:
            # CWE-703: If the expected PID token is not an integer, the line is skipped.
            # This can hide issues with 'ps' output or parsing logic.
            continue

        # The complete string of the process as per the OpenAPI schema.
        process_string = line

        # CWE-400: Uncontrolled Resource Consumption
        # The `regex.search` operation is performed on potentially very long lines
        # and without any CPU or time limits, making it susceptible to
        # catastrophic backtracking with certain regex patterns.
        if regex.search(process_string):
            matching_processes.append(
                ProcessInfo(processId=pid, processString=process_string)
            )

    return matching_processes


# --- Main execution block for Uvicorn ---

if __name__ == "__main__":
    # The 'Error' schema component is referenced in the OpenAPI specification,
    # and FastAPI will include it in the generated OpenAPI documentation even if
    # not explicitly used as a response_model for an endpoint, as long as it's defined.
    uvicorn.run(app, host="0.0.0.0", port=5000)
