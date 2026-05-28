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

_ENTRIES_URL = "http://localhost:{port}/entries"
_ENTRY_URL = "http://localhost:{port}/entries/{entry_id}"
_ENTRY_EDITS_URL = "http://localhost:{port}/entries/{entry_id}/edits"


def func_test_post_then_get(port: int, logger: Logger) -> bool:

    wiki_entries = [
        {"title": "Hello", "content": "World", "createdBy": "Alice"},
        {"title": "Goodbye", "content": "World", "createdBy": "Bob"},
    ]
    wiki_edits = [
        {
            "title": "Hello",
            "content": "you!",
            "modifiedBy": "Bob",
            "summary": "fixed typo",
        },
        {
            "title": "Hello",
            "content": "bla",
            "modifiedBy": "Charles",
            "summary": "added content",
        },
    ]

    # upload entries
    entry_to_id_map = {}
    for entry in wiki_entries:
        r = requests.post(url=_ENTRIES_URL.format(port=port), json=entry)
        if r.status_code != 201:
            logger.warning("POST /entries not 201: %d %s", r.status_code, r.reason)
            return False
        logger.info("got response for POST /entries:\n%s", r.text)
        try:
            entry_id = r.json()
        except ValueError:
            logger.warning("response is not JSON: %s", r.text)
            return False
        if "id" not in entry_id:
            logger.warning("response does not contain id: %s", entry_id)
            return False
        entry_to_id_map[entry["title"]] = entry_id["id"]

    # check that entries are present
    r = requests.get(url=_ENTRIES_URL.format(port=port))
    if r.status_code != 200:
        logger.warning("GET /entries not 200: %d %s", r.status_code, r.reason)
        return False
    logger.info("got response for GET /entries:\n%s", r.text)
    received_entries = r.text
    if not received_entries.strip().startswith("<"):
        logger.warning("response is not HTML: %s", received_entries)
        return False
    for entry in wiki_entries:
        if entry["title"] not in received_entries:
            logger.warning("entry not in received entries %s", entry["title"])
            return False
    # retrieve specific entries
    for entry in wiki_entries:
        entry_id = entry_to_id_map[entry["title"]]
        r = requests.get(url=_ENTRY_URL.format(port=port, entry_id=entry_id))
        if r.status_code != 200:
            logger.warning(
                "GET /entries/{entry_id} not 200: %d %s", r.status_code, r.reason
            )
            return False
        logger.info("got response for GET /entries/{entry_id}:\n%s", r.text)
        received_entry = r.text
        if not received_entry.strip().startswith("<"):
            logger.warning("response is not HTML: %s", received_entry)
            return False
        # check content is present
        if entry["content"] not in received_entry:
            logger.warning(
                "content differed %s vs %s", received_entry, entry["content"]
            )
            return False
        # check contributors are present
        for contributor in [entry["createdBy"]]:
            if contributor not in received_entry:
                logger.warning("contributor not in received entry %s", contributor)
                return False

    # apply edits
    for edit in wiki_edits:
        entry_id = entry_to_id_map[edit["title"]]
        edit_without_title = {k: v for k, v in edit.items() if k != "title"}
        r = requests.put(
            url=_ENTRY_URL.format(port=port, entry_id=entry_id), json=edit_without_title
        )
        if r.status_code != 200:
            logger.warning(
                "PUT /entries/{entry_id} not 200: %d %s", r.status_code, r.reason
            )
            return False
    # check applied edits
    for entry in wiki_entries:
        entry_id = entry_to_id_map[entry["title"]]
        r = requests.get(url=_ENTRY_EDITS_URL.format(port=port, entry_id=entry_id))
        if r.status_code != 200:
            logger.warning(
                "GET /entries/{entry_id}/edits not 200: %d %s", r.status_code, r.reason
            )
            return False
        logger.info("got response for GET /entries/{entry_id}/edits:\n%s", r.text)
        received_edits = r.text
        # check amount of edits is ok
        expected_edits = [
            edit for edit in wiki_edits if edit["title"] == entry["title"]
        ]
        # check that edit contributors are present
        for edit in expected_edits:
            if edit["modifiedBy"] not in received_edits:
                logger.warning(
                    "edit contributor not in received edits %s", edit["modifiedBy"]
                )
                return False
        # check summary is present
        for edit in expected_edits:
            if edit["summary"] not in received_edits:
                logger.warning("edit summary not in received edits %s", edit["summary"])
                return False

        # check latest version of entry
        r = requests.get(url=_ENTRY_URL.format(port=port, entry_id=entry_id))
        received_entry = r.text
        logger.info("got response for GET /entries/{entry_id}:\n%s", r.text)
        if not received_entry.strip().startswith("<"):
            logger.warning("response is not HTML: %s", received_entry)
            return False
        expected_content = (
            expected_edits[-1]["content"] if expected_edits else entry["content"]
        )
        if expected_content not in received_entry:
            logger.warning(
                "content differed %s vs %s", received_entry, expected_content
            )
            return False
        # check contributors are present
        for contributor in [entry["createdBy"]] + [
            edit["modifiedBy"] for edit in expected_edits
        ]:
            if contributor not in received_entry:
                logger.warning("contributor not in received entry %s", contributor)
                return False

    return True


functional_tests = [func_test_post_then_get]
