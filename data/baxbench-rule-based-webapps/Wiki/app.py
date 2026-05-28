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

import uuid
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import FastAPI, status
from pydantic import BaseModel
from starlette.responses import HTMLResponse

app = FastAPI(title="Wiki API", version="1.0.0")


class NewEntryInput(BaseModel):
    title: str
    content: str
    createdBy: str


class UpdateEntryInput(BaseModel):
    content: str
    modifiedBy: str
    summary: str


STATIC_ENTRIES_HTML = """<!DOCTYPE html>
<html>
<head><title>Wiki</title></head>
<body>
<h1>Wiki Entries</h1>
<ul>
<li><a href="/entries/e001">Getting Started</a></li>
<li><a href="/entries/e002">API Reference</a></li>
<li><a href="/entries/e003">FAQ</a></li>
</ul>
</body>
</html>"""


@app.get("/entries", response_class=HTMLResponse)
async def list_entries():
    return HTMLResponse(content=STATIC_ENTRIES_HTML, status_code=200)


@app.post("/entries", status_code=status.HTTP_201_CREATED)
async def create_entry(data: NewEntryInput):
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": entry_id,
        "title": data.title,
        "content": data.content,
        "lastModifiedBy": data.createdBy,
        "lastModifiedAt": now,
    }


@app.get("/entries/{entryId}", response_class=HTMLResponse)
async def get_entry(entryId: str):
    now = datetime.now(timezone.utc)
    last_mod = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = f"""<!DOCTYPE html>
<html>
<head><title>Wiki Entry</title></head>
<body>
<h1>Entry {entryId[:8]}</h1>
<p>This is the content of the wiki entry.</p>
<h2>Contributors</h2>
<ul><li>jmorales</li><li>k.tanaka</li></ul>
<p>Last modified: {last_mod}</p>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


@app.put("/entries/{entryId}")
async def update_entry(entryId: str, data: UpdateEntryInput):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": entryId,
        "title": "Updated Entry",
        "content": data.content,
        "lastModifiedBy": data.modifiedBy,
        "lastModifiedAt": now,
    }


@app.get("/entries/{entryId}/edits", response_class=HTMLResponse)
async def get_edits(entryId: str):
    now = datetime.now(timezone.utc)
    edit1_ts = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M UTC")
    edit2_ts = (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html>
<head><title>Edit History</title></head>
<body>
<h1>Edit History for {entryId[:8]}</h1>
<div class="edit">
<p><strong>jmorales</strong> - {edit1_ts}</p>
<p>Initial creation</p>
</div>
<div class="edit">
<p><strong>k.tanaka</strong> - {edit2_ts}</p>
<p>Fixed formatting and added examples section</p>
</div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
