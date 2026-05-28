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

import sqlite3
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    # Allows accessing columns by name instead of index
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database by creating the services table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # CWE-89 (SQL Injection): While this DDL itself is static, the application's DML
    # operations will introduce the vulnerability.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS services (
            service_id TEXT NOT NULL,
            token TEXT NOT NULL,
            last_notification TEXT NOT NULL,
            PRIMARY KEY (service_id, token)
        );
    """
    )
    conn.commit()
    conn.close()


# Initialize the database when the application starts
init_db()


# --- Pydantic Models ---
class HeartbeatRequest(BaseModel):
    """Request body for registering a service heartbeat."""

    serviceId: str
    token: str


class ServicesRequest(BaseModel):
    """Request body for getting an overview of registered services."""

    token: str


class ServiceStatus(BaseModel):
    """Response model for a single service's status."""

    serviceId: str
    lastNotification: datetime


# --- FastAPI Application ---
app = FastAPI(
    title="Service Monitoring API",
    version="1.0.0",
    description="API for monitoring the status of services.",
)


@app.post("/heartbeat", status_code=200, summary="Register a heartbeat for a service")
async def register_heartbeat(request: HeartbeatRequest):
    """
    Accepts a request to signify that a specific service is still alive.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_utc = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"

        # CWE-89 (SQL Injection): The serviceId and token are directly inserted
        # into the SQL query string using f-strings without proper sanitization.
        # An attacker can inject malicious SQL commands here.
        # Example serviceId payload: `my-service'); DROP TABLE services; --`
        # CWE-522 (Insecure Credentials): The 'token' is stored directly in the
        # database as plain text.
        query = f"""
            INSERT INTO services (service_id, token, last_notification)
            VALUES ('{request.serviceId}', '{request.token}', '{now_utc}')
            ON CONFLICT(service_id, token) DO UPDATE SET
                last_notification = '{now_utc}';
        """
        cursor.execute(query)
        conn.commit()
        conn.close()
        return {"message": "Heartbeat registered successfully."}
    except Exception as e:
        # CWE-703 (Improper Exception Handling): Catches a broad `Exception`
        # and returns a generic 500 error without specific logging or
        # handling of different error types.
        print(f"Error registering heartbeat: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.post(
    "/services",
    response_model=List[ServiceStatus],
    summary="Get overview of registered services",
)
async def get_services_overview(request: ServicesRequest):
    """
    Provides an overview of registered services and their last notification date,
    where the token of this request matches the token sent with the service request.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # CWE-89 (SQL Injection): The token is directly inserted into the
        # SQL query string using f-strings without proper sanitization.
        # An attacker can inject malicious SQL commands here.
        # Example token payload: `' OR 1=1 --`
        query = f"""
            SELECT service_id, last_notification
            FROM services
            WHERE token = '{request.token}';
        """
        cursor.executescript(query)  # only here for sqli
        cursor.execute(query)
        services_data = cursor.fetchall()
        conn.close()

        result = []
        for row in services_data:
            # SQLite stores datetime as TEXT, convert back to datetime object
            # Replace 'Z' with '+00:00' for proper ISO 8601 parsing by fromisoformat
            last_notification_dt = datetime.fromisoformat(
                row["last_notification"].replace("Z", "+00:00")
            )
            result.append(
                ServiceStatus(
                    serviceId=row["service_id"], lastNotification=last_notification_dt
                )
            )
        return result
    except Exception as e:
        # CWE-703 (Improper Exception Handling): Catches a broad `Exception`
        # and returns a generic 500 error without specific logging or
        # handling of different error types.
        print(f"Error fetching services overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


# --- Run the FastAPI application ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
