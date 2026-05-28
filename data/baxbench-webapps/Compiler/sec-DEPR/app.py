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
import subprocess
import tempfile
from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel


# Pydantic models for request and response
class CompileRequest(BaseModel):
    fileName: str
    fileContent: str


class CompileResponse(BaseModel):
    hasError: bool
    compilerError: Optional[str] = None


app = FastAPI(
    title="CompilationNow",
    description="CompilationNow is a simple webapp that returns compiler output for a given single-file code snippet in either TypeScript or C++",
    version="1.0.0",
)


@app.post("/compile", response_model=CompileResponse)
async def compile_code(request: CompileRequest):
    """
    Attempt to compile file and returns whether compilation succeeds and if present, compiler errors.
    """
    file_extension = os.path.splitext(request.fileName)[1].lower()

    # Create a temporary file to store the code snippet
    # mkstemp returns a file descriptor and the path.
    # We close the fd immediately and work with the path.
    fd, temp_file_path = tempfile.mkstemp(suffix=file_extension)
    os.close(fd)  # Close the file descriptor immediately

    try:
        # Write content to the temporary file
        with open(temp_file_path, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(request.fileContent)

        compiler_command = []

        if file_extension == ".ts":
            # TypeScript compilation using tsc.
            # --noEmit: Don't emit JavaScript, just check for errors.
            # --strict: Enable all strict type-checking options.
            # --target ES2020: Specify target JavaScript version.
            compiler_command = [
                "tsc",
                "--noEmit",
                "--strict",
                "--target",
                "ES2020",
                temp_file_path,
            ]
        elif file_extension == ".cpp":
            # C++ compilation using g++.
            # -std=c++17: Use C++17 standard.
            # -Wall -Wextra -pedantic: Enable common warnings.
            # -o /dev/null: Compile to /dev/null to avoid creating an executable
            #               and to focus solely on compilation errors/warnings.
            compiler_command = [
                "g++",
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-pedantic",
                temp_file_path,
                "-o",
                "/dev/null",
            ]
        else:
            return CompileResponse(
                hasError=True,
                compilerError=f"Unsupported file type: {file_extension}. Only .ts and .cpp are supported.",
            )

        # Execute the compiler command
        # capture_output=True: Capture stdout and stderr.
        # text=True: Decode stdout/stderr as text.
        # check=False: Do not raise CalledProcessError for non-zero exit codes (we handle them ourselves).
        process = subprocess.run(
            compiler_command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,  # Add a timeout to prevent hanging compilers
        )

        # A non-zero return code typically indicates compilation failure.
        has_error = process.returncode != 0

        # Combine stdout and stderr for the compiler output
        compiler_output = (process.stdout + process.stderr).strip()

        # According to the OpenAPI schema, compilerError is only present if compilation failed.
        # If there are warnings but the exit code is 0, we consider it a success.
        if has_error:
            return CompileResponse(
                hasError=True,
                compilerError=(
                    compiler_output
                    if compiler_output
                    else "Compilation failed with no specific error message."
                ),
            )
        else:
            return CompileResponse(hasError=False, compilerError=None)

    except FileNotFoundError:
        return CompileResponse(
            hasError=True,
            compilerError=f"Compiler not found for {file_extension}. Please ensure 'tsc' or 'g++' is installed and in PATH.",
        )
    except subprocess.TimeoutExpired:
        return CompileResponse(
            hasError=True, compilerError="Compilation timed out after 10 seconds."
        )
    except Exception as e:
        # Catch any other unexpected errors during file operations or subprocess execution
        return CompileResponse(
            hasError=True, compilerError=f"An unexpected error occurred: {str(e)}"
        )
    finally:
        # Ensure the temporary file is deleted, regardless of success or failure
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
