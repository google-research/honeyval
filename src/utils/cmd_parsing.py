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

import shlex
from typing import List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit


def sanitize_curl(cmd: str, restrict_to_url: Optional[str]) -> List[str]:
    """
    Parses a curl command and replaces the target URL with the provided URL.
    It ensures that the command is a valid curl command with exactly one URL.
    In the input, it is possible that the curl command is not the first command
    in the command chain. Also, the payload may contain complex string escaping, as
    the input might be used for testing the security of databases in webapps, so the
    parsing needs to reflect delicate string handling and escaping. Note that the function
    might move the URL to the end of the command if the original command is not well-formed,
    but it will never change any other part of the command.

    Args:
        cmd: The input curl command as a string.
        restrict_to_url: The URL to replace in the curl command. If None, no replacement is done.

    Returns:
        A list of command components with the URL replaced.

    Raises:
        ValueError: If the command is not a valid curl command or if there are multiple URLs.
    """
    separators = {";", "|", "&", "&&", "||"}

    def _split_tolerant(raw_command: str) -> List[str]:
        tokens: List[str] = []
        buffer: List[str] = []
        index = 0
        length = len(raw_command)
        state: str | None = None
        punctuation = {";", "|", "&"}

        def _flush() -> None:
            nonlocal buffer
            if buffer:
                tokens.append("".join(buffer))
                buffer = []

        while index < length:
            char = raw_command[index]
            next_char = raw_command[index + 1] if index + 1 < length else ""

            if state is None:
                if char.isspace():
                    _flush()
                elif char == "'":
                    state = "single"
                elif char == '"':
                    state = "double"
                elif char in punctuation:
                    _flush()
                    if char in {"|", "&"} and next_char == char:
                        tokens.append(char + next_char)
                        index += 1
                    else:
                        tokens.append(char)
                else:
                    buffer.append(char)
            elif state == "single":
                if char == "'":
                    state = None
                else:
                    buffer.append(char)
            else:
                if char == "\\" and index + 1 < length:
                    buffer.append(raw_command[index + 1])
                    index += 1
                elif char == '"':
                    after = raw_command[index + 1] if index + 1 < length else ""
                    if index + 1 == length or after.isspace() or after in ";|&":
                        state = None
                    else:
                        buffer.append(char)
                else:
                    buffer.append(char)

            index += 1

        _flush()
        return tokens

    def _split_strict(raw_command: str) -> List[str]:
        lexer = shlex.shlex(raw_command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        return list(lexer)

    def _merge_urls(base_url: str, target_url: str) -> str:
        base_parts = urlsplit(base_url)
        target_parts = urlsplit(target_url)

        base_path = base_parts.path.rstrip("/")
        merged_path = (
            f"{base_path}{target_parts.path}" if target_parts.path else base_path
        )

        return urlunsplit(
            (
                base_parts.scheme,
                base_parts.netloc,
                merged_path,
                target_parts.query,
                target_parts.fragment,
            )
        )

    parser_used = "strict"
    try:
        tokens = _split_strict(cmd)
    except ValueError:
        tokens = _split_tolerant(cmd)
        parser_used = "tolerant"

    command_start: int | None = None
    for token_index, token in enumerate(tokens):
        if token == "curl" and (
            token_index == 0 or tokens[token_index - 1] in separators
        ):
            command_start = token_index
            break

    if command_start is None:
        raise ValueError("No valid curl commands found in this command.")

    command_end = len(tokens)
    for token_index in range(command_start + 1, len(tokens)):
        if tokens[token_index] in separators:
            command_end = token_index
            break

    curl_tokens = tokens[command_start:command_end]

    url_positions: List[Tuple[int, str]] = [
        (token_index, token)
        for token_index, token in enumerate(curl_tokens)
        if token.startswith("http://") or token.startswith("https://")
    ]

    if len(url_positions) != 1:
        raise ValueError(
            "This command is not a valid curl command: "
            f"{' '.join(curl_tokens)}.\n"
            "A valid curl command must contain exactly one target url."
        )

    if restrict_to_url is not None:
        url_index, target_url = url_positions[0]
        replacement_url = _merge_urls(restrict_to_url, target_url)

        if parser_used == "tolerant" and url_index != len(curl_tokens) - 1:
            curl_tokens = [
                token
                for token_index, token in enumerate(curl_tokens)
                if token_index != url_index
            ]
            curl_tokens.append(replacement_url)
        else:
            curl_tokens[url_index] = replacement_url

    return curl_tokens
