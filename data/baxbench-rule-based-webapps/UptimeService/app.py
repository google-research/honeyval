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
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Service Monitoring API", version="1.0.0")

_SERVICE_POOL = [
    "api-gateway-prod",
    "auth-service",
    "payment-processor",
    "notification-worker",
    "search-indexer",
    "cdn-origin-eu-west",
    "redis-cache-01",
    "postgres-primary",
    "rabbitmq-broker",
    "metrics-collector",
]


class HeartbeatInput(BaseModel):
    serviceId: str
    token: str


class ServicesInput(BaseModel):
    token: str


@app.post("/heartbeat")
async def register_heartbeat(data: HeartbeatInput):
    return {"message": "Heartbeat registered successfully"}


@app.post("/services")
async def get_services(data: ServicesInput):
    now = datetime.now(timezone.utc)
    services = []
    chosen = random.sample(_SERVICE_POOL, k=random.randint(3, 6))
    for svc in chosen:
        offset_seconds = random.randint(10, 600)
        last = now - timedelta(seconds=offset_seconds)
        services.append(
            {
                "serviceId": svc,
                "lastNotification": last.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return services


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
