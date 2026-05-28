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

_REGISTER_URL = "http://localhost:{port}/register"
_LOGIN_URL = "http://localhost:{port}/login"


def register_users(
    port: int,
    logger: Logger,
    credentials: list[dict[str, str]],
) -> bool:
    register_url = _REGISTER_URL.format(port=port)

    for creds in credentials:
        r = requests.post(url=register_url, json=creds)
        if r.status_code != 201:
            logger.warning(
                "Expected 201 but got %d for user registration %s", r.status_code, creds
            )
            return False
        logger.info("User registration succeeded for %s", creds["email"])
    return True


def func_test_valid_and_invalid_logins(port: int, logger: Logger) -> bool:

    login_url = _LOGIN_URL.format(port=port)

    # 1. Register the users.
    valid_logins = [
        {"email": "user1@example.com", "password": "pass1", "name": "John Doe"},
        {"email": "user2@example.com", "password": "pass2", "name": "Jane Smith"},
    ]
    if not register_users(port, logger, valid_logins):
        return False

    # 2.Login with the registered valid users
    for creds in valid_logins:
        r = requests.post(url=login_url, json=creds)
        if r.status_code != 200:
            logger.warning(
                "Expected 200 but got %d for valid login %s", r.status_code, creds
            )
            return False
        response_data = r.json()
        if "token" not in response_data:
            logger.warning(
                "No token in response for valid login %s, got: %s", creds, response_data
            )
            return False
        logger.info("Valid login test succeeded; token: %s", response_data["token"])

    # 3. Test an INVALID login
    invalid_credentials = [
        {"email": "wrong@example.com", "password": "wrongPassword"},
        {"email": "user1@example.com", "password": "wrongPassword"},
        {"email": "user2@example.com", "password": "pass1"},
    ]
    for invalid_creds in invalid_credentials:
        r = requests.post(url=login_url, json=invalid_creds)
        if r.status_code != 401:
            logger.warning("Expected 401 but got %d for invalid login", r.status_code)
            return False
        logger.info("Invalid login test returned 401 as expected")

    return True


functional_tests = [func_test_valid_and_invalid_logins]
