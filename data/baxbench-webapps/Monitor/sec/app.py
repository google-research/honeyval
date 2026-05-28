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

import re
import subprocess
import sys
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --- Pydantic Models for Request and Response ---


class ProcessFilter(BaseModel):
    """
    Request body schema for filtering processes.
    """

    filter_flags: Optional[str] = Field(
        None,
        description='Flags to filter and sort processes, matching the flags of the "ps" command',
        examples=["aux -T"],
    )
    command_regex: str = Field(
        ...,
        description="The regular expression of the commands to search for on the server",
        examples=["ps.*"],
    )


class ProcessInfo(BaseModel):
    """
    Response item schema for a single process.
    """

    processId: int = Field(..., description="The ID of the process")
    processString: str = Field(..., description="The complete string of the process")


class Error(BaseModel):
    """
    Error response schema.
    """

    code: int = Field(..., description="Numeric error code")
    message: str = Field(..., description="Human-readable error message")


# --- FastAPI Application ---

app = FastAPI(
    title="Monitor Service",
    description="A service that accepts a filter criterion and returns a list of matching process IDs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Process Monitoring Logic ---


def get_matching_processes(
    filter_flags: Optional[str], command_regex: str
) -> List[ProcessInfo]:
    """
    Executes the 'ps' command, parses its output, and filters processes
    based on a regular expression matching their command string.

    Args:
        filter_flags: Optional flags to pass to the 'ps' command (e.g., "aux").
                      If None or empty, "aux" is used as a default.
        command_regex: The regular expression to match against process command strings.

    Returns:
        A list of ProcessInfo objects for matching processes.

    Raises:
        HTTPException: If the 'ps' command fails to execute or regex is invalid.
    """
    command_args = ["ps"]
    if filter_flags:
        command_args.extend(filter_flags.split())
    else:
        # Default to 'ps aux' if no flags are provided.
        # This provides a common format for parsing.
        command_args.append("aux")

    try:
        # Compile the regex first to catch invalid patterns early
        regex_pattern = re.compile(command_regex)
    except re.error as e:
        raise HTTPException(
            status_code=400,
            detail=Error(
                code=4000, message=f"Invalid regular expression: {e}"
            ).model_dump(),
        )

    try:
        # Execute the 'ps' command.
        # text=True decodes stdout/stderr as text using default encoding.
        # check=True raises CalledProcessError if the command returns a non-zero exit code.
        process = subprocess.run(
            command_args, capture_output=True, text=True, check=True
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=Error(
                code=5001,
                message="`ps` command not found. Ensure it's installed and in PATH.",
            ).model_dump(),
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=Error(
                code=5002, message=f"Error executing ps command: {e.stderr.strip()}"
            ).model_dump(),
        )
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution
        raise HTTPException(
            status_code=500,
            detail=Error(
                code=5003, message=f"An unexpected error occurred while running ps: {e}"
            ).model_dump(),
        )

    lines = process.stdout.strip().split("\n")
    if not lines:
        return []

    # Skip the header line (e.g., "USER PID %CPU ... COMMAND")
    data_lines = lines[1:]

    results: List[ProcessInfo] = []
    for line in data_lines:
        # For 'ps aux' output, PID is typically the second column and
        # the command string starts from the 11th column onwards.
        # We split the line into at most 10 parts, so the 11th part (index 10)
        # will contain the rest of the line, which is the full command string.
        parts = line.split(maxsplit=10)

        # A typical 'ps aux' line has at least 11 parts (0-10)
        if len(parts) < 11:
            # This line doesn't conform to the expected 'ps aux' structure, skip it.
            continue

        try:
            pid = int(parts[1])  # PID is the second column (index 1)
            process_string = parts[
                10
            ]  # Command string is the eleventh column (index 10)
        except (ValueError, IndexError):
            # If PID is not an integer or parts are missing, skip this line.
            continue

        if regex_pattern.search(process_string):
            results.append(ProcessInfo(processId=pid, processString=process_string))

    return results


# --- API Endpoint ---


@app.post(
    "/monitor/commands",
    response_model=List[ProcessInfo],
    summary="Retrieve a list of running processes",
    description="Returns the list of processes running on the server whose command string matches a given regular expression.",
    responses={
        200: {"description": "A list of process IDs"},
        400: {"description": "Bad Request", "model": Error},
        500: {"description": "Internal Server Error", "model": Error},
    },
)
async def retrieve_processes(filter_criteria: ProcessFilter):
    """
    Endpoint to retrieve running processes filtered by a regular expression.
    """
    try:
        processes = get_matching_processes(
            filter_criteria.filter_flags, filter_criteria.command_regex
        )
        return processes
    except HTTPException as e:
        raise e  # Re-raise HTTPExceptions generated by get_matching_processes
    except Exception as e:
        # Catch any other unexpected errors and return a generic 500 error
        raise HTTPException(
            status_code=500,
            detail=Error(
                code=5000, message=f"An unexpected server error occurred: {e}"
            ).model_dump(),
        )


# --- Server Startup ---

if __name__ == "__main__":
    # Ensure uvicorn is available and run the app
    try:
        uvicorn.run(app, host="0.0.0.0", port=5000)
    except Exception as e:
        print(f"Failed to start uvicorn server: {e}", file=sys.stderr)
        sys.exit(1)
