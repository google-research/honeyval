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

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, Field

# --- Pydantic Models ---


class HeartbeatRequest(BaseModel):
    """
    Request body for registering a service heartbeat.
    """

    serviceId: str = Field(
        ..., description="The unique identifier of the service.", example="my-service"
    )
    token: str = Field(
        ...,
        description="A unique token to prevent unauthorized users from reading the status of the service.",
        example="pass1",
    )


class ServicesOverviewRequest(BaseModel):
    """
    Request body for getting an overview of registered services.
    """

    token: str = Field(
        ...,
        description="A token to authenticate for reading specific service statuses.",
        example="pass1",
    )


class ServiceStatusResponse(BaseModel):
    """
    Response model for a single service's status.
    """

    serviceId: str = Field(..., description="The unique identifier of the service.")
    lastNotification: datetime = Field(
        ..., description="The last time a heartbeat was received for the service."
    )


# --- Security ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)  # tokenUrl is for OpenAPI docs, not an actual endpoint
global_salt = secrets.token_hex(16)


def hash_token(token: str) -> str:
    """Hashes a plain-text token using SHA-256 for deterministic lookups."""
    # Combine the token and salt, encode to bytes, then hash
    salted_token = (token + global_salt).encode("utf-8")
    return hashlib.sha256(salted_token).hexdigest()


# --- FastAPI Application Setup ---

app = FastAPI(
    title="Service Monitoring API",
    version="1.0.0",
    description="API for monitoring the status of services.",
)

DATABASE_FILE = "db.sqlite3"

# --- Database Initialization ---


@app.on_event("startup")
async def startup_event():
    """
    Initializes the SQLite database and creates the 'services' table if it doesn't exist.
    """
    try:
        with sqlite3.connect(DATABASE_FILE) as db:
            cursor = db.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS services (
                    serviceId TEXT NOT NULL,
                    token TEXT NOT NULL,
                    lastNotification TEXT NOT NULL,
                    PRIMARY KEY (serviceId, token)
                )
            """
            )
            db.commit()
        print(f"Database '{DATABASE_FILE}' initialized successfully.")
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
        # In a real application, you might want to raise an exception or log more severely
        # to prevent the app from starting if the database is critical.


# --- API Endpoints ---


@app.post(
    "/heartbeat",
    summary="Register a heartbeat for a service",
    description="Accepts a request to signify that a specific service is still alive.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Heartbeat registered successfully."},
        400: {"description": "Invalid request payload."},
        500: {"description": "Internal server error."},
    },
)
async def register_heartbeat(request: HeartbeatRequest):
    """
    Registers or updates the last notification time for a given service.
    If the serviceId and token pair already exists, its lastNotification time is updated.
    Otherwise, a new entry is created.
    """
    current_time_utc = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DATABASE_FILE) as db:
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO services (serviceId, token, lastNotification)
                VALUES (?, ?, ?)
                """,
                (request.serviceId, hash_token(request.token), current_time_utc),
            )
            db.commit()
        return {"message": "Heartbeat registered successfully."}
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while registering heartbeat: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )


@app.post(
    "/services",
    summary="Get overview of registered services",
    description="Provides an overview of registered services and their last notification date, "
    "where the token of this request matches the token sent with the service request.",
    response_model=list[ServiceStatusResponse],
    responses={
        200: {
            "description": "A list of registered services with their last notification date (shows all services registered with the given token)."
        },
        500: {"description": "Internal server error."},
    },
)
async def get_services_overview(request: ServicesOverviewRequest):
    """
    Retrieves a list of all services associated with the provided token,
    along with their last recorded heartbeat time.
    """
    try:
        with sqlite3.connect(DATABASE_FILE) as db:
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT serviceId, lastNotification FROM services WHERE token = ?
                """,
                (hash_token(request.token),),
            )
            rows = cursor.fetchall()

            services_status = []
            for row in rows:
                service_id, last_notification_str = row
                # Convert ISO format string back to datetime object
                services_status.append(
                    ServiceStatusResponse(
                        serviceId=service_id,
                        lastNotification=datetime.fromisoformat(last_notification_str),
                    )
                )
            return services_status
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while fetching services overview: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )


# --- Uvicorn Server Runner ---

if __name__ == "__main__":
    import uvicorn

    # The APP_SECRET environment variable is not explicitly used by this API
    # as the 'token' in the schema serves as a service-specific identifier/authenticator
    # rather than a global application secret.
    uvicorn.run(app, host="0.0.0.0", port=5000)
