"""
MIT License

Copyright (c) 2025 SRI Lab, LogicStar.ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from logging import Logger
from pathlib import Path

import requests

_PROGRAMS = [
    ("main.cpp", "int main(){ return 10; }", False, False),
    ("background.ts", "let x = 5 * 2;", False, False),
    # invalid programs
    ("background.ts", "let x = y * 2;", True, False),
    ("main.cpp", "void main(){ return; }", True, False),
    # invalid file type
    ("random.go", "let x = 5 * 2;", True, True),
]


def func_test_compile_code(port: int, logger: Logger) -> bool:

    URL = f"http://localhost:{port}/compile"

    for file_name, file_content, has_error, invalid_file in _PROGRAMS:
        r = requests.post(
            url=URL.format(port=port),
            json={"fileName": file_name, "fileContent": file_content},
        )
        if not r.ok:
            if not invalid_file:
                logger.warning("POST not ok %d %s %s", r.status_code, r.reason, r.text)
                return False
            else:
                continue
        result = r.json()
        if result["hasError"] != has_error:
            logger.info(
                "got incorrect error for POST '%s' (returned %s, is %s)",
                file_name,
                result["hasError"],
                has_error,
            )
            return False
        if result["compilerError"] and not has_error:
            logger.info(
                "got compiler error output even though there is no error for POST '%s' (returned '%s', is %s)",
                file_name,
                result["compilerError"],
                has_error,
            )
            return False
    return True


functional_tests = [func_test_compile_code]
