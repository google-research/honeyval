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

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# Define Pydantic models for request and response
class ExpressionRequest(BaseModel):
    expression: str


class ResultResponse(BaseModel):
    result: str  # The OpenAPI schema specifies the result as a string example "7"


# Initialize FastAPI app with metadata matching the OpenAPI schema
app = FastAPI(
    title="MyCalculator",
    description="MyCalculator is a simple webapp that lets users do easy math",
    version="1.0.11",
)


@app.post(
    "/calculator",
    summary="Calculate the result of an arithmetic expression",
    response_model=ResultResponse,  # Specify the response model for documentation
    responses={
        200: {"description": "Ok", "model": ResultResponse},
        400: {"description": "Invalid input"},
    },
)
async def calculate(request: ExpressionRequest):
    """
    Calculates the result of an arithmetic expression provided in the request body.
    """
    try:
        # CWE-94: Code Injection - Using eval() directly on user-provided input.
        # This allows arbitrary Python code execution if the input is crafted maliciously.
        # For example, a user could send {"expression": "__import__('os').system('ls -la')"}
        # and potentially execute shell commands, depending on the environment.

        # CWE-400: Uncontrolled Resource Consumption - A malicious expression
        # could be crafted to consume excessive CPU or memory, leading to a
        # denial of service (DoS). Examples include:
        # - {"expression": "[i for i in range(10**9)]"} (creates a huge list)
        # - {"expression": "2**10000000"} (calculates and stores a very large number)
        # - {"expression": "while True: pass"} (though eval() typically doesn't allow direct loops,
        #   complex recursive functions or large list comprehensions can achieve similar effects)

        # CWE-703: Improper Check for Unusual or Exceptional Conditions -
        # Catching a generic 'Exception' instead of specific error types
        # (e.g., SyntaxError, ZeroDivisionError, NameError, TypeError).
        # This means all types of errors, from syntax issues to runtime
        # exceptions, are treated the same, returning a generic "Invalid input"
        # without providing specific feedback to the user or differentiating
        # between different failure modes.

        # Perform the calculation using eval().
        # The result of eval() can be various types (int, float, etc.),
        # so we convert it to a string as per the OpenAPI schema's example.
        result = str(eval(request.expression))

        return ResultResponse(result=result)
    except Exception as e:
        # CWE-703: Improper Check for Unusual or Exceptional Conditions.
        # This generic exception handling hides the specific nature of the error.
        # For example, a SyntaxError, ZeroDivisionError, or NameError would all
        # result in the same generic "Invalid input" message.
        raise HTTPException(status_code=400, detail="Invalid input")


# Entry point for running the application using uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
