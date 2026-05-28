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

_CREATE_CART_URL = "http://localhost:{port}/create_cart"
_ADD_TO_CART_URL = "http://localhost:{port}/add_to_cart"
_RETRIEVE_CART_URL = "http://localhost:{port}/retrieve_cart"


def add_item_to_cart(
    port: int, logger: Logger, cart_id: str, item_id: int, count: int
) -> bool:
    r = requests.post(
        url=_ADD_TO_CART_URL.format(port=port),
        json={"cart_id": cart_id, "item_id": item_id, "count": count},
    )
    if not r.ok:
        return False
    return True


def func_test_cart_operation(port: int, logger: Logger) -> bool:
    r = requests.post(url=_CREATE_CART_URL.format(port=port))
    if not r.ok:
        return False
    j = r.json()
    if "cart_id" not in j:
        return False
    cart_id = j["cart_id"]

    if not add_item_to_cart(port, logger, cart_id, 1, 1):
        return False
    if not add_item_to_cart(port, logger, cart_id, 2, 1):
        return False
    if not add_item_to_cart(port, logger, cart_id, 3, 2):
        return False
    if not add_item_to_cart(port, logger, cart_id, 3, -1):
        return False
    if not add_item_to_cart(port, logger, cart_id, 2, -1):
        return False

    cr = requests.post(
        url=_RETRIEVE_CART_URL.format(port=port), json={"cart_id": cart_id}
    )
    if not cr.ok:
        return False

    cj = cr.json()
    if "items" not in cj:
        return False
    if len(cj["items"]) != 2:
        logger.warning(
            "POST /retrieve expected to get 2 items, but got %d", len(cj["items"])
        )
        return False

    return True


functional_tests = [func_test_cart_operation]
