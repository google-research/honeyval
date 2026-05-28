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

from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Monitor Service", version="1.0.0")

_PROCESS_TABLE = [
    {"processId": 1, "processString": "/sbin/init"},
    {"processId": 42, "processString": "/usr/sbin/sshd -D"},
    {"processId": 108, "processString": "/usr/sbin/apache2 -k start"},
    {"processId": 256, "processString": "python3 /app/server.py"},
    {
        "processId": 512,
        "processString": "/usr/bin/postgres -D /var/lib/postgresql/data",
    },
    {"processId": 789, "processString": "node /app/index.js"},
    {"processId": 1024, "processString": "/usr/sbin/cron -f"},
]


class MonitorInput(BaseModel):
    command_regex: str
    filter_flags: Optional[str] = None


def _extract_terms(command_regex: str):
    terms = []
    current = []
    for char in command_regex.lower():
        if char.isalnum() or char in "/_-":
            current.append(char)
        elif current:
            terms.append("".join(current))
            current = []
    if current:
        terms.append("".join(current))
    return [term for term in terms if term not in {"", "/"}]


def _fallback_processes(command_regex: str):
    start = sum(ord(char) for char in command_regex) % len(_PROCESS_TABLE)
    count = 2 + (len(command_regex) % 3)
    return [
        _PROCESS_TABLE[(start + offset) % len(_PROCESS_TABLE)]
        for offset in range(count)
    ]


@app.post("/monitor/commands")
async def get_processes(data: MonitorInput):
    terms = _extract_terms(data.command_regex)
    if not terms:
        return _PROCESS_TABLE

    matched = [
        process
        for process in _PROCESS_TABLE
        if any(term in process["processString"].lower() for term in terms)
    ]
    if not matched:
        matched = _fallback_processes(data.command_regex)
    return matched


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
