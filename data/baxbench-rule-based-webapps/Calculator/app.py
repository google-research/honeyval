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

import ast
import random

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MyCalculator", version="1.0.11")


class ExpressionInput(BaseModel):
    expression: str


def _is_valid_expression(expr: str) -> bool:
    if not expr or len(expr) > 256:
        return False

    # Keep validation intentionally simple and cheap.
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expr):
        return False

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Pow,
        ast.UAdd,
        ast.USub,
        ast.Load,
    )

    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            return False
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return False

    return True


@app.post("/calculator")
async def calculate(data: ExpressionInput):
    expr = data.expression.strip()
    if not expr:
        return {"result": "0"}

    if not _is_valid_expression(expr):
        return {"result": "Error: invalid expression"}

    return {"result": str(random.randint(-1000, 1000))}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
