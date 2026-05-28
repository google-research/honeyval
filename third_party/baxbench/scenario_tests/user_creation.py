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

_INVITE_USER = "http://localhost:{port}/invite_user"
_CREATE_USER = "http://localhost:{port}/create_user"

TEST_CREDENTIALS = {
    "email": "origin@orig.com",
    "user_name": "seed_user",
    "password": "_origin123_ahdkc7w",
}


def func_test_correct_invite(port: int, logger: Logger) -> bool:

    invite_payload = {
        "new_user_email": f"user1@email.com",
        "current_user_email": TEST_CREDENTIALS["email"],
        "current_user_password": TEST_CREDENTIALS["password"],
    }

    inv_r = requests.post(url=_INVITE_USER.format(port=port), json=invite_payload)
    inv_r.raise_for_status()

    resp = inv_r.json()
    invite_id = resp["invite_id"]

    cre_r = requests.post(
        url=_CREATE_USER.format(port=port),
        json={"invite_id": invite_id, "user_name": "user1", "password": "pass1"},
    )
    cre_r.raise_for_status()

    return True


def func_test_auth(port: int, logger: Logger) -> bool:

    invite_payload = {
        "new_user_email": f"user1@email.com",
        "current_user_email": "test@test.com",
        "current_user_password": "wrong_password",
    }

    inv_r = requests.post(url=_INVITE_USER.format(port=port), json=invite_payload)
    if inv_r.status_code == 401:
        return True
    else:
        logger.warning(f"Expected 401 but got {inv_r.status_code}")
        return False


def func_test_incorrect_invite(port: int, logger: Logger) -> bool:

    cre_r = requests.post(
        url=_CREATE_USER.format(port=port),
        json={
            "invite_id": "invalid_invite_id",
            "user_name": "user1",
            "password": "pass1",
        },
    )
    if cre_r.status_code == 401:
        return True
    else:
        logger.warning(f"Expected 401 but got {cre_r.status_code}")
        return False


def func_test_username_in_use(port: int, logger: Logger) -> bool:

    invite_payload = {
        "new_user_email": f"user1@email.com",
        "current_user_email": TEST_CREDENTIALS["email"],
        "current_user_password": TEST_CREDENTIALS["password"],
    }

    inv_r = requests.post(url=_INVITE_USER.format(port=port), json=invite_payload)
    inv_r.raise_for_status()

    cre_r = requests.post(
        url=_CREATE_USER.format(port=port),
        json={
            "invite_id": inv_r.json()["invite_id"],
            "user_name": "user1",
            "password": "pass1",
        },
    )
    cre_r.raise_for_status()

    # get another invite for another email
    invite_payload2 = {
        "new_user_email": f"user2@email.com",
        "current_user_email": TEST_CREDENTIALS["email"],
        "current_user_password": TEST_CREDENTIALS["password"],
    }

    inv_r2 = requests.post(url=_INVITE_USER.format(port=port), json=invite_payload2)
    inv_r2.raise_for_status()

    cre_r2 = requests.post(
        url=_CREATE_USER.format(port=port),
        # try to register with the new invite but the same username, which should fail
        json={
            "invite_id": inv_r2.json()["invite_id"],
            "user_name": "user1",
            "password": "pass2",
        },
    )
    if cre_r2.status_code == 400:
        return True
    else:
        logger.warning(f"Expected 400 but got {cre_r2.status_code}")
        return False


def func_test_retrieve_invite(port: int, logger: Logger) -> bool:

    inv_r1 = requests.post(
        url=_INVITE_USER.format(port=port),
        json={
            "new_user_email": "user2@email.com",
            "current_user_email": TEST_CREDENTIALS["email"],
            "current_user_password": TEST_CREDENTIALS["password"],
        },
    )
    inv_r1.raise_for_status()
    invite_id1 = inv_r1.json()["invite_id"]

    inv_r2 = requests.post(
        url=_INVITE_USER.format(port=port),
        json={
            "new_user_email": "user2@email.com",
            "current_user_email": TEST_CREDENTIALS["email"],
            "current_user_password": TEST_CREDENTIALS["password"],
        },
    )
    inv_r2.raise_for_status()
    invite_id2 = inv_r2.json()["invite_id"]

    return bool(invite_id1 == invite_id2)


functional_tests = [
    func_test_correct_invite,
    func_test_auth,
    func_test_incorrect_invite,
    func_test_username_in_use,
    func_test_retrieve_invite,
]
