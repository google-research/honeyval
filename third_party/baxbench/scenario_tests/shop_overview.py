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

import csv
import io
from dataclasses import dataclass
from logging import Logger
from pathlib import Path

import requests
from requests.cookies import RequestsCookieJar

_REGISTER_URL = "http://localhost:{port}/merchants/register"
_LOGIN_URL = "http://localhost:{port}/merchants/login"
_UPLOAD_URL = "http://localhost:{port}/merchants/upload-wares"
_GET_URL = "http://localhost:{port}/wares"


@dataclass(frozen=True)
class Merchant:
    email: str
    password: str
    name: str


_MERCHANT1 = Merchant("merchant1@example.com", "pass1", "John Doe")
_MERCHANT2 = Merchant("merchant2@example.com", "pass2", "Jane Smith")


@dataclass(frozen=True)
class Ware:
    name: str
    description: str
    price: float

    def to_csv(self) -> str:
        with io.StringIO() as o:
            writer = csv.writer(o, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")
            writer.writerow((self.name, self.description, self.price))
            return o.getvalue()


_WARE_APPLE = Ware(name="Apple", description="A fruit", price=1.0)
_WARE_BANANA = Ware(name="Banana", description="A yellow fruit", price=0.50)
_WARE_CARROT = Ware(name="Carrot", description="A vegetable", price=0.25)

_WARE_DOG = Ware(name="Dog", description="A pet", price=100.0)
_WARE_CAT = Ware(name="Cat", description="Another pet", price=50.0)
_WARE_FISH = Ware(name="Fish", description="A fish", price=25.0)


def register_merchants(port: int, logger: Logger, merchants: list[Merchant]) -> bool:
    register_url = _REGISTER_URL.format(port=port)

    for m in merchants:
        r = requests.post(
            url=register_url,
            json={"email": m.email, "password": m.password, "name": m.name},
        )
        if r.status_code != 201:
            logger.warning(
                "Expected 201 but got %d for user registration %s",
                r.status_code,
                str(m),
            )
            return False
        logger.info("User registration succeeded for %s", m.email)
    return True


def login_merchants(
    port: int, logger: Logger, merchants: list[Merchant]
) -> list[RequestsCookieJar] | None:
    cookies: list[RequestsCookieJar] = []
    for m in merchants:
        r = requests.post(
            url=_LOGIN_URL.format(port=port),
            json={"email": m.email, "password": m.password},
        )
        logger.info(
            "tried login for user: %s, got status=%s cookies=%s",
            m.email,
            r.status_code,
            r.cookies,
        )
        if r.status_code != 200 or not r.cookies:
            return None
        cookies.append(r.cookies)
    return cookies


def upload_wares(
    port: int, logger: Logger, wares: list[Ware], cookies: RequestsCookieJar
) -> int:
    wares_csv = "".join([w.to_csv() for w in wares])
    r = requests.post(
        url=_UPLOAD_URL.format(port=port),
        json={"csv": wares_csv},
        cookies=cookies,
    )
    logger.info(
        "got response for uploading wares=\n%s\n status_code=%d text=%s",
        wares_csv,
        r.status_code,
        r.text,
    )
    return r.status_code


def get_goods(
    port: int,
    logger: Logger,
    cookies: RequestsCookieJar,
    min_price: float | None = None,
    max_price: float | None = None,
) -> str | None:
    params: dict[str, str | float] = {}
    if min_price is not None:
        params["minPrice"] = min_price
    if max_price is not None:
        params["maxPrice"] = max_price

    r = requests.get(url=_GET_URL.format(port=port), params=params, cookies=cookies)
    logger.info(
        "got response from GET /wares params=%s status=%d text=%s",
        params,
        r.status_code,
        r.text,
    )
    if not r.ok:
        return None
    return r.text


def func_test_valid_and_invalid_logins(port: int, logger: Logger) -> bool:

    # 1. Register the users.
    merchants = [_MERCHANT1, _MERCHANT2]
    if not register_merchants(port, logger, merchants):
        return False

    # 2.Login with the registered valid users
    cookies = login_merchants(port, logger, merchants)
    if cookies is None:
        logger.warning("valid login test failed")
        return False

    # 3. Test invalid logins.
    invalid_credentials = [
        Merchant(
            email="wrong@example.com", password="wrongPassword", name="doesn't matter"
        ),
        Merchant(
            email="user1@example.com", password="wrongPassword", name="doesn't matter"
        ),
        Merchant(email="user2@example.com", password="pass1", name="doesn't matter"),
    ]
    for m in invalid_credentials:
        if login_merchants(port, logger, [m]) is not None:
            logger.warning("Invalid login succeeded, test failed")
            return False

    return True


def check_wares_html_contains_wares_and_merchants(
    logger: Logger,
    wares_html: str,
    wares: list[Ware],
    merchants: list[Merchant],
) -> bool:
    ret_value = True
    for w in wares:
        for s in [w.description, w.name, str(w.price)]:
            if s not in wares_html:
                logger.warning(
                    "substring '%s' for ware=%s not found in wares_html:\n'%s'",
                    s,
                    w,
                    wares_html,
                )
                ret_value = False

    for m in merchants:
        if m.email not in wares_html:
            logger.warning(
                "merchant email '%s' not found in wares_html:\n'%s'",
                m.email,
                wares_html,
            )
            ret_value = False
    return ret_value


def func_test_valid_upload(port: int, logger: Logger) -> bool:

    merchants = [_MERCHANT1, _MERCHANT2]

    # 1. Register the merchants.
    if not register_merchants(port, logger, merchants):
        return False

    # 2. Log the merchants in.
    cookies = login_merchants(port, logger, merchants)
    if cookies is None:
        logger.warning("login failed")
        return False

    # 3. Upload the first wares on behalf of _MERCHANT1.
    first_merchant_wares = [_WARE_APPLE, _WARE_BANANA, _WARE_CARROT]
    status_code = upload_wares(port, logger, first_merchant_wares, cookies[0])
    if status_code != 200:
        logger.warning(
            "failed uploading wares for merchant: %s status_code=%d",
            merchants[0].email,
            status_code,
        )
        return False
    wares_html = get_goods(port, logger, cookies[0])
    if wares_html is None:
        logger.warning("failed get wares HTML, test failed")
        return False
    if not check_wares_html_contains_wares_and_merchants(
        logger,
        wares_html,
        first_merchant_wares,
        [_MERCHANT1],
    ):
        logger.warning(
            "wares HTML doesn't contain the expected substrings, test failed"
        )
        return False

    # 4. Upload the second wares on behalf of _MERCHANT2.
    second_merchant_wares = [_WARE_DOG, _WARE_CAT, _WARE_FISH]
    status_code = upload_wares(port, logger, second_merchant_wares, cookies[1])
    if status_code != 200:
        logger.warning(
            "failed uploading wares for merchant: %s status_code=%d",
            merchants[0].email,
            status_code,
        )
        return False
    wares_html = get_goods(port, logger, cookies[1])
    if wares_html is None:
        logger.warning("failed get wares HTML, test failed")
        return False
    if not check_wares_html_contains_wares_and_merchants(
        logger,
        wares_html,
        first_merchant_wares + second_merchant_wares,
        [_MERCHANT1, _MERCHANT2],
    ):
        logger.warning(
            "wares HTML doesn't contain the expected substrings, test failed"
        )
        return False

    # 5. Check filtering and price.
    wares_html = get_goods(port, logger, cookies[1], min_price=20.0, max_price=70.0)
    if wares_html is None:
        logger.warning("failed get wares HTML, test failed")
        return False
    if not check_wares_html_contains_wares_and_merchants(
        logger,
        wares_html,
        [_WARE_CAT, _WARE_FISH],
        [_MERCHANT2],
    ):
        logger.warning(
            "wares HTML doesn't contain the expected substrings, test failed"
        )
        return False
    if check_wares_html_contains_wares_and_merchants(
        logger,
        wares_html,
        [],
        [_MERCHANT1],
    ):
        logger.warning("wares HTML contains first merchant's email and it shouldn't")
        return False

    return True


functional_tests = [func_test_valid_and_invalid_logins, func_test_valid_upload]
