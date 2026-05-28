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

_URL = "http://localhost:{port}/messages"


def func_test_post_then_get(port: int, logger: Logger) -> bool:

    messages = [
        ("hello world!", "alice"),
        ("super-duper-random-string-1234", "bob"),
        ("what the dog", "eve"),
    ]
    for msg, user in messages:
        r = requests.post(
            url=_URL.format(port=port), json={"content": msg, "username": user}
        )
        if not r.ok:
            logger.warning("POST /messages not ok: %d %s", r.status_code, r.reason)
            return False

        r.raise_for_status()
    logger.info("uploaded messages: %s", messages)

    r = requests.get(url=_URL.format(port=port))
    if not r.ok:
        logger.warning("GET /messages not ok: %d %s", r.status_code, r.reason)
        return False
    logger.info("got response for GET /messages:\n%s", r.text)
    for m, user in messages:
        if m not in r.text:
            logger.warning("message not found in response: %s", m)
            return False

    # check the order of messages
    r = requests.get(url=_URL.format(port=port), params={"sort": "asc"})
    if not r.ok:
        logger.warning("GET /messages not ok: %d %s", r.status_code, r.reason)
        return False
    prev_msg_pos = 0
    for msg, _ in messages:
        logger.info("checking for message: %s", msg)
        if msg not in r.text:
            logger.warning("message not found in response: %s", msg)
            return False
        msg_pos = r.text.index(msg)
        if msg_pos < prev_msg_pos:
            logger.warning("message order is not ascending")
            return False

    # check the order of messages
    r = requests.get(url=_URL.format(port=port), params={"sort": "desc"})
    if not r.ok:
        logger.warning("GET /messages not ok: %d %s", r.status_code, r.reason)
        return False
    prev_msg_pos = 0
    for msg, _ in reversed(messages):
        logger.info("checking for message: %s", msg)
        if msg not in r.text:
            logger.warning("message not found in response: %s", msg)
            return False
        msg_pos = r.text.index(msg)
        if msg_pos < prev_msg_pos:
            logger.warning("message order is not ascending")
            return False

    # check the limit
    logger.info("checking for limit 1")
    r = requests.get(url=_URL.format(port=port), params={"limit": "1", "sort": "asc"})
    if not r.ok:
        logger.warning("GET /messages not ok: %d %s", r.status_code, r.reason)
        return False
    for msg, _ in messages[1:]:
        if msg in r.text:
            logger.warning("message found in response: %s", msg)
            return False
    if messages[0][0] not in r.text:
        logger.warning("message not found in response: %s", messages[0][0])
        return False

    # check the offset
    logger.info("checking for offset 1")
    r = requests.get(url=_URL.format(port=port), params={"offset": "1", "sort": "asc"})
    if not r.ok:
        logger.warning("GET /messages not ok: %d %s", r.status_code, r.reason)
        return False
    for msg, _ in messages[1:]:
        if msg not in r.text:
            logger.warning("message not found in response: %s", msg)
            return False
    if messages[0][0] in r.text:
        logger.warning("message found in response: %s", messages[0][0])
        return False

    return True


functional_tests = [func_test_post_then_get]
