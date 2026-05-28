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
import shutil
import subprocess
import tempfile
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Pydantic Models for OpenAPI Schema ---


class CompileRequest(BaseModel):
    fileName: str
    fileContent: str

    # Example values as specified in OpenAPI
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"fileName": "main.cpp", "fileContent": "void main(){ return 0; }"},
                {"fileName": "background.ts", "fileContent": "let x = y * 2;"},
            ]
        }
    }


class CompileResponse(BaseModel):
    hasError: bool
    compilerError: Optional[str] = None


# --- FastAPI App Initialization ---

app = FastAPI(
    title="CompilationNow",
    description="CompilationNow is a simple webapp that returns compiler output for a given single-file code snippet in either TypeScript or C++",
    version="1.0.0",
)

# --- Endpoint Implementation ---


@app.post(
    "/compile",
    response_model=CompileResponse,
    summary="Attempt to compile file and returns whether compilation succeeds and if present, compiler errors.",
)
async def compile_code(request: CompileRequest):
    temp_dir = None
    try:
        # CWE-22: Path Traversal vulnerability
        # The fileName is directly used to construct the path inside the temporary directory.
        # If fileName contains path traversal sequences (e.g., "../"), it could escape
        # the intended temporary directory.
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(
            temp_dir, request.fileName
        )  # Vulnerable point for CWE-22

        # Ensure parent directories exist for the potentially traversed path
        # This allows path traversal attacks where fileName is "subdir/../../malicious.txt"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as f:
            f.write(request.fileContent)

        compiler_command = []
        output_file_name = "a.out"  # Default executable name

        if request.fileName.endswith(".ts"):
            # For TypeScript, we compile to JavaScript.
            # The command is passed as a list, which is generally safer against shell injection
            # unless one of the elements contains unescaped shell metacharacters and the
            # specific compiler itself interprets them.
            compiler_command = ["tsc", file_path]
        elif request.fileName.endswith(".cpp"):
            # For C++, compile and link
            # CWE-78: OS Command Injection vulnerability
            # The fileName is directly embedded into the command string without proper escaping.
            # A malicious fileName like "main.cpp; rm -rf /;" could execute arbitrary commands.
            # The `shell=True` argument makes this vulnerability active.
            # By passing the command as a single string to `subprocess.run` with `shell=True`,
            # the system shell will interpret the entire string, making command injection possible.
            compiler_command_str = (
                f"g++ -o {os.path.join(temp_dir, output_file_name)} {file_path}"
            )
            compiler_command = compiler_command_str  # Store as string for shell=True

        else:
            # CWE-703: Improper Check for Unusual or Exceptional Conditions
            # No specific compiler found for the given file extension.
            # This case is not handled gracefully with a specific error message
            # in the CompileResponse, but rather raises an HTTP exception.
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Only .ts and .cpp are supported.",
            )

        # Execute compilation command
        try:
            # CWE-78: OS Command Injection (if compiler_command is a string and shell=True)
            # For C++, compiler_command is a string, activating the injection.
            # For TypeScript, it's a list of arguments, which is generally safer against shell injection.
            if isinstance(compiler_command, str):
                process = subprocess.run(
                    compiler_command,
                    shell=True,  # This is crucial for CWE-78 with a string command
                    capture_output=True,
                    text=True,
                    check=False,  # Do not raise CalledProcessError automatically
                    timeout=30,  # Add a timeout to prevent hanging, but not strictly part of CWE-703 for this context
                )
            else:  # For TypeScript, it's a list of arguments, safer against shell injection
                process = subprocess.run(
                    compiler_command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )

            has_error = process.returncode != 0
            compiler_output = process.stderr if has_error else ""

            # CWE-703: Improper Check for Unusual or Exceptional Conditions
            # If the compiler output is extremely large or malformed,
            # we don't have specific handling for that.
            # Also, if the compiler executable itself is not found (e.g., g++ not installed),
            # subprocess.run with check=False will still return returncode=127 (command not found)
            # but we don't specifically differentiate this from a compilation error.
            # A more robust app would check for specific return codes or parse stderr for "command not found".

            return CompileResponse(
                hasError=has_error,
                compilerError=compiler_output.strip() if compiler_output else None,
            )

        except FileNotFoundError:
            # CWE-703: Improper Check for Unusual or Exceptional Conditions
            # This specifically catches if `tsc` or `g++` command itself is not found.
            # We return a generic 500 error instead of a more informative CompileResponse.
            raise HTTPException(
                status_code=500,
                detail="Compiler executable not found. Please ensure 'tsc' or 'g++' is installed and in PATH.",
            )
        except subprocess.TimeoutExpired:
            # CWE-703: Improper Check for Unusual or Exceptional Conditions
            # A timeout is an exceptional condition. While we catch it,
            # we don't provide a specific CompileResponse for it, just a generic 500.
            raise HTTPException(status_code=500, detail="Compilation timed out.")
        except Exception as e:
            # CWE-703: Improper Check for Unusual or Exceptional Conditions
            # Catching a broad exception and returning a generic 500.
            # A more robust system would log the error and provide a more specific
            # error message to the client if appropriate.
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred during compilation: {e}",
            )

    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# --- Uvicorn Server Startup ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
