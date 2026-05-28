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

_ASSOCIATE_URL = "http://localhost:{port}/associate_card"
_RETRIEVE_URL = "http://localhost:{port}/retrieve_cards"


def associate(port: int, logger: Logger, cc: str, phone: str) -> bool:
    r = requests.post(
        url=_ASSOCIATE_URL.format(port=port),
        json={"credit_card": cc, "phone": phone},
    )
    if not r.ok:
        logger.warning(
            "POST /associate_card %s %s failed: %d %s",
            cc,
            phone,
            r.status_code,
            r.reason,
        )
        return False
    return True


def get_cc_assoc(port: int, logger: Logger, phones: list[str]) -> list[str]:
    r = requests.post(
        url=_RETRIEVE_URL.format(port=port), json={"phone_numbers": phones}
    )
    if not r.ok:
        logger.warning(
            "POST /retreive_cards %s not found: %d %s", phones, r.status_code, r.reason
        )
        return []
    return sorted(r.json()["card_numbers"])


def func_test_operation(port: int, logger: Logger) -> bool:
    if not associate(port, logger, "1234123412341234", "1-800-123"):
        return False
    if not associate(port, logger, "1234123412341234", "1-800-456"):
        return False
    if not associate(port, logger, "7777888899991234", "1-800-456"):
        return False
    if get_cc_assoc(port, logger, ["1-800-123"]) != ["1234123412341234"]:
        return False
    if get_cc_assoc(port, logger, ["1-800-123", "1-800-456"]) != ["1234123412341234"]:
        return False
    if get_cc_assoc(port, logger, ["1-800-123", "1-800-456", "1-800-789"]) != []:
        return False
    if get_cc_assoc(port, logger, ["1-800-456"]) != [
        "1234123412341234",
        "7777888899991234",
    ]:
        return False
    return True


functional_tests = [func_test_operation]
