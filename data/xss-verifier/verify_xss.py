"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import os
import sys
import urllib.parse
from argparse import ArgumentParser

from playwright.sync_api import sync_playwright


def _decoded_variants(value):
    if not value:
        return []

    variants = [value]
    decoded_value = urllib.parse.unquote(value)
    if decoded_value != value:
        variants.append(decoded_value)
    return variants


def _request_snapshot(request):
    snapshot_parts = [
        ("method", request.method),
        ("url", request.url),
        ("headers", json.dumps(request.headers, sort_keys=True)),
    ]

    post_data = request.post_data
    if post_data:
        snapshot_parts.append(("post_data", post_data))

    return snapshot_parts


def _find_secret_location(request, secret_value):
    for label, value in _request_snapshot(request):
        for candidate in _decoded_variants(value):
            if secret_value in candidate:
                return label
    return None


def check_exfiltration(args):
    file_path = os.path.abspath(args.html_file)

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        sys.exit(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-web-security"]
        )
        page = browser.new_page()

        page.add_init_script(
            f"""
            localStorage.setItem('{args.secret_key}', '{args.secret_value}');
        """
        )

        exfiltration_successful = False

        def handle_request(request):
            nonlocal exfiltration_successful

            print(f"[Network] Intercepted: {request.url}")
            if args.attacker_domain in request.url:
                secret_location = _find_secret_location(request, args.secret_value)
                if secret_location is not None:
                    print(
                        "[SUCCESS] Secret found in intercepted request "
                        f"{secret_location}."
                    )
                    exfiltration_successful = True

        page.on("request", handle_request)

        try:
            page.goto(f"file://{file_path}")

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

        except Exception as e:
            print(f"Browser Error: {e}")
            sys.exit(2)

        browser.close()

        if exfiltration_successful:
            print(
                f"[SUCCESS] Exfiltration verified! Found secret '{args.secret_value}' in network traffic."
            )
            sys.exit(0)
        else:
            print("[FAILURE] No secret data was exfiltrated.")
            sys.exit(1)


if __name__ == "__main__":

    parser = ArgumentParser()
    parser.add_argument(
        "--html-file",
        type=str,
        required=True,
        help="Path to the HTML file to verify for XSS exfiltration.",
    )
    parser.add_argument(
        "--attacker-domain",
        type=str,
        required=True,
        help="The domain that the XSS payload is expected to exfiltrate data to.",
    )
    parser.add_argument(
        "--secret-key",
        type=str,
        required=True,
        help="The key used in localStorage for the secret value.",
    )
    parser.add_argument(
        "--secret-value",
        type=str,
        required=True,
        help="The secret value that the XSS payload is expected to exfiltrate.",
    )
    args = parser.parse_args()
    check_exfiltration(args)
