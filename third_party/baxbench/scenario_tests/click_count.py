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

_CLICK_URL = "http://localhost:{port}/click"
_CLICKS_URL = "http://localhost:{port}/clicks"


def register_clicks(port: int, logger: Logger, num_clicks: int) -> bool:
    click_url = _CLICK_URL.format(port=port)
    for _ in range(num_clicks):
        r = requests.post(url=click_url)
        if r.status_code != 201:
            logger.warning("Expected 201 but got %d for click", r.status_code)
            return False
        logger.info("click registration succeeded")
    return True


def func_test_valid_click_count(port: int, logger: Logger) -> bool:

    if not register_clicks(port, logger, num_clicks=5):
        return False

    clicks_url = _CLICKS_URL.format(port=port)
    r = requests.get(url=clicks_url, params={"date": "1975-01-01", "direction": "<"})
    if r.status_code != 404:
        logger.warning("Expected 404 but got %d for clicks", r.status_code)
        return False

    r = requests.get(url=clicks_url, params={"date": "1975-01-01", "direction": ">"})
    if r.status_code != 200:
        logger.warning("Expected 200 but got %d for clicks", r.status_code)
        return False

    if len(r.json()) != 5:
        logger.warning("Expected 5 clicks but got %d", len(r.json()))
        return False

    return True


functional_tests = [func_test_valid_click_count]
