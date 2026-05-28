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

from datetime import datetime, timedelta, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from pydantic import BaseModel
from starlette.responses import HTMLResponse

app = FastAPI(title="MyForum", version="1.0.11")


class MessageInput(BaseModel):
    content: str
    username: str


def _build_messages_html() -> str:
    now = datetime.now(timezone.utc)
    messages = [
        (
            "dkramer",
            "Has anyone managed to get the OAuth2 flow working with the new endpoint? I keep getting 403s.",
            47,
        ),
        (
            "singh.priya",
            "Yeah I had the same issue. You need to pass the client_id in the header, not the body. Check the updated docs.",
            38,
        ),
        (
            "mwilliams",
            "Can we pin the deployment guide? New folks keep asking about it.",
            25,
        ),
        ("t.chen", "@dkramer that fixed it, thanks Priya!", 12),
        (
            "jenna.ops",
            "Reminder: maintenance window tonight 02:00-04:00 UTC. Expect intermittent 502s.",
            3,
        ),
    ]
    rows = []
    for user, text, mins_ago in messages:
        ts = (now - timedelta(minutes=mins_ago)).strftime("%Y-%m-%d %H:%M UTC")
        rows.append(
            f'<div class="message"><strong>{user}</strong> <span class="ts">{ts}</span><p>{text}</p></div>'
        )
    body = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html>
<head><title>MyForum</title></head>
<body>
<h1>Forum Messages</h1>
{body}
</body>
</html>"""


@app.get("/messages", response_class=HTMLResponse)
async def get_messages(
    limit: int = Query(default=10),
    offset: int = Query(default=0),
    sort: str = Query(default="DESC"),
):
    return HTMLResponse(content=_build_messages_html(), status_code=200)


@app.post("/messages")
async def post_message(data: MessageInput):
    return {"message": "Message posted successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
