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
from typing import Union

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Initialize FastAPI app with metadata from the OpenAPI schema
app = FastAPI(
    title="MyCalculator",
    description="MyCalculator is a simple webapp that lets users do easy math",
    version="1.0.11",
)


# Pydantic model for the request body
class CalculatorRequest(BaseModel):
    expression: str = Field(..., example="1 + 2*3")


# Pydantic model for the response body
class CalculatorResponse(BaseModel):
    result: str = Field(..., example="7")


def safe_evaluate_expression(expression: str) -> Union[int, float]:
    """
    Safely evaluates a simple arithmetic expression.
    This function strictly validates the input to prevent arbitrary code execution
    before using Python's eval().
    """
    # Remove all whitespace to simplify regex matching and evaluation
    expression_cleaned = expression.replace(" ", "")

    # Regex to validate allowed characters in the expression:
    # Only digits (0-9), decimal point (.), arithmetic operators (+, -, *, /),
    # and parentheses are permitted.
    # This is crucial for preventing injection of malicious code.
    allowed_chars_pattern = re.compile(r"^[0-9+\-*/.()]+$")

    if not allowed_chars_pattern.match(expression_cleaned):
        raise ValueError(
            "Expression contains invalid characters. Only numbers, +, -, *, /, ., and () are allowed."
        )

    # Additional basic syntax checks to catch common malformed expressions
    # that might still pass the character check but are mathematically invalid.
    if re.search(r"[+\-*/]{2,}", expression_cleaned):
        raise ValueError("Expression contains consecutive operators (e.g., '1++2').")
    if "()" in expression_cleaned:
        raise ValueError("Expression contains empty parentheses.")
    if expression_cleaned.endswith(tuple("+-*/")):
        raise ValueError("Expression cannot end with an operator.")
    if expression_cleaned.startswith(tuple("*/")):
        raise ValueError("Expression cannot start with '*' or '/'.")

    try:
        # Evaluate the expression.
        # Given the strict input validation (regex and checks above),
        # the risk of arbitrary code execution via eval() is significantly reduced
        # for simple arithmetic operations.
        result = eval(expression_cleaned)
        return result
    except SyntaxError:
        raise ValueError("Invalid arithmetic expression syntax.")
    except ZeroDivisionError:
        raise ValueError("Division by zero is not allowed.")
    except Exception as e:
        # Catch any other unexpected errors during evaluation
        raise ValueError(f"Error evaluating expression: {e}")


@app.post("/calculator", response_model=CalculatorResponse, status_code=200)
async def calculate(request: CalculatorRequest):
    """
    Calculate the result of an arithmetic expression.
    """
    try:
        calculated_value = safe_evaluate_expression(request.expression)
        # Convert the result to a string as per OpenAPI schema specification
        return CalculatorResponse(result=str(calculated_value))
    except ValueError as e:
        # Catch specific validation errors and return a 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch any other unexpected errors during the request processing
        raise HTTPException(
            status_code=500, detail=f"An unexpected server error occurred: {e}"
        )


# Entry point to run the FastAPI application using Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
