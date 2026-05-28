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

import random
import uuid
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import FastAPI, Query, status

app = FastAPI(title="Click Tracking API", version="1.0.0")


def _generate_clicks(n: int = 5):
    now = datetime.now(timezone.utc)
    clicks = []
    for i in range(n):
        offset_minutes = random.randint(1, 1440 * 7)
        ts = now - timedelta(minutes=offset_minutes)
        clicks.append(
            {
                "id": uuid.uuid4().hex[:12],
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    clicks.sort(key=lambda c: c["timestamp"], reverse=True)
    return clicks


@app.post("/click", status_code=status.HTTP_201_CREATED)
async def register_click():
    return {"message": "Click registered successfully"}


@app.get("/clicks")
async def get_clicks(date: str = Query(...), direction: str = Query(...)):
    return _generate_clicks()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
