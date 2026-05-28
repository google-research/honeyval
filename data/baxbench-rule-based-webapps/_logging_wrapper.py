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

"""
Logging wrapper for rule-based honeypot apps.

This script is copied into the Docker container's working directory alongside
app.py.  It imports the real FastAPI app, attaches a request/response logging
middleware, and starts uvicorn.  Every request is written as a JSONL event to
the path given by METADATA_LOG_PATH (injected via environment variable and
backed by a host bind-mount so the events persist after the container exits).

Event format mirrors HttpLLMHoneypot:
  {"time_in": float, "time_out": float, "event": "COMMAND",
   "tokens_consumed": 0, "tokens_generated": 0,
   "in": <request JSON str>, "out": <response body str>}
"""

import json
import os
import time

import uvicorn
from app import app
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

METADATA_PATH = os.environ["METADATA_LOG_PATH"]


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        time_in = time.time()
        body = await request.body()

        request_repr = json.dumps(
            {
                "method": request.method,
                "path": str(request.url.path),
                "query": str(request.url.query),
                "headers": dict(request.headers),
                "body": body.decode("utf-8", errors="replace"),
            }
        )

        response = await call_next(request)

        chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunks.append(chunk.encode("utf-8"))
            else:
                chunks.append(chunk)
        response_body = b"".join(chunks)

        time_out = time.time()

        event = {
            "time_in": time_in,
            "time_out": time_out,
            "event": "COMMAND",
            "tokens_consumed": 0,
            "tokens_generated": 0,
            "in": request_repr,
            "out": response_body.decode("utf-8", errors="replace"),
        }

        with open(METADATA_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


app.add_middleware(RequestLoggerMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
