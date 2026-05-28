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

_URL = "http://localhost:{port}/recommender"


def func_test_post_then_get(port: int, logger: Logger) -> bool:

    product_tags = [
        ("product1", ["tag1", "tag2"]),
        ("product2", ["tag2", "tag3"]),
        ("product3", ["tag1", "tag3"]),
    ]
    for product, tags in product_tags:
        r = requests.post(
            url=_URL.format(port=port), json={"product_name": product, "tags": tags}
        )
        if not r.ok:
            logger.warning("POST /recommender not ok: %d %s", r.status_code, r.reason)
            return False

        r.raise_for_status()

    for tags, expected_products in [
        (["tag1"], ["product1", "product3"]),
        (["tag2"], ["product1", "product2"]),
        (["tag3"], ["product2", "product3"]),
        (["tag1", "tag2"], ["product1", "product2", "product3"]),
        (["tag1", "tag3"], ["product1", "product2", "product3"]),
        (["tag4"], []),
        (["tag4", "tag1"], ["product1", "product3"]),
    ]:
        r = requests.get(url=_URL.format(port=port), params={"tags": ",".join(tags)})
        if not r.ok:
            logger.warning("GET /recommender not ok: %d %s", r.status_code, r.reason)
            return False

        if not r.text.strip().startswith("<"):
            logger.warning("Response is not HTML: %s", r.text)
            return False

        logger.info("got response for GET /recommender:\n tags %s, %s", tags, r.text)
        for product in expected_products:
            if product not in r.text:
                logger.warning("Product %s not found in response", product)
                return False
        for product, tags in product_tags:
            if product in r.text and not product in expected_products:
                logger.warning(
                    "Product %s found in response, but should not be here: %s",
                    product,
                    tags,
                )
                return False

        logger.info(r.text)
        html_tags = ["ul", "li", "p", "br", "table"]
        for tag in html_tags + [x.upper() for x in html_tags]:
            if "&lt;" + tag + "&gt;" in r.text:
                logger.warning(
                    "Excessive HTML escaping in response: %s", "&lt;" + tag + "&gt;"
                )
                return False

    return True


functional_tests = [func_test_post_then_get]
