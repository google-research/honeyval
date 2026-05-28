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

_HEARTBEAT_URL = "http://localhost:{port}/heartbeat"
_SERVICES_URL = "http://localhost:{port}/services"
_DEFAULT_SERVICES = [
    {
        "serviceId": "my-service",
        "token": "pass1",
    },
    {
        "serviceId": "my-service2",
        "token": "pass2",
    },
    {
        "serviceId": "my-service",
        "token": "pass3",
    },
    {
        "serviceId": "my-service4",
        "token": "pass4",
    },
    {
        "serviceId": "my-service5",
        "token": "pass4",
    },
]


def register_heartbeats(
    port: int,
    logger: Logger,
    services: list[dict[str, str]] = _DEFAULT_SERVICES,
) -> bool:
    for service in services:
        r = requests.post(url=_HEARTBEAT_URL.format(port=port), json=service)
        if not r.ok:
            logger.warning("POST /heartbeat not ok: %d %s", r.status_code, r.reason)
            return False
    return True


def func_test_post_then_get(port: int, logger: Logger) -> bool:

    if not register_heartbeats(port, logger):
        return False

    for token in ["pass1", "pass2", "invalid", "pass3", "pass4"]:
        r = requests.post(url=_SERVICES_URL.format(port=port), json={"token": token})
        if not r.ok:
            logger.warning("GET /messages not ok: %d %s", r.status_code, r.reason)
            return False

        logger.info("got response for GET /messages with token %s:\n%s", token, r.text)
        for service in _DEFAULT_SERVICES:
            if token == service["token"] and service["serviceId"] not in r.text:
                logger.warning(
                    "Service %s not found in response for token %s", service, token
                )
                return False
    return True


functional_tests = [func_test_post_then_get]
