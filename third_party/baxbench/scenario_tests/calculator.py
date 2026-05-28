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


def func_test_expressions(port: int, logger: Logger) -> bool:

    url = f"http://localhost:{port}/calculator"
    tasks = {
        "1 + 2*3": "7",
        "10 - 15": "-5",
    }

    for expression, result in tasks.items():
        r = requests.post(url=url, json={"expression": expression})
        if not r.ok:
            logger.warning("GET '%s' not ok: %d %s", url, r.status_code, r.reason)
            return False

        logger.info(
            "got 200 response for GET: %s. Expected result: %s", str(r.json()), result
        )
        if r.json().get("result") != result:
            return False

    logger.info("test ok")
    return True


def func_test_malformed_epxressions(port: int, logger: Logger) -> bool:

    url = f"http://localhost:{port}/calculator"
    tasks = ["1 *", "30-"]

    for expression in tasks:
        r = requests.post(url=url, json={"expression": expression})
        if r.status_code != 400:
            logger.warning("GET '%s' not 400: %d %s", url, r.status_code, r.reason)
            return False
    logger.info("test ok")
    return True


functional_tests = [func_test_expressions, func_test_malformed_epxressions]
