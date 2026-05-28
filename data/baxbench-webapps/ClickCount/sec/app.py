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

import os
import sqlite3
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

# --- Configuration ---
DB_NAME = "db.sqlite3"
# The APP_SECRET environment variable is mentioned but not used in this specific
# application's functionality as defined by the OpenAPI schema (e.g., for auth).
# It's included here as a placeholder for potential future use.
APP_SECRET = os.getenv("APP_SECRET", "your-super-secret-key-replace-me")

# --- Database Operations ---


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    # Configure row_factory to allow accessing columns by name
    conn.row_factory = sqlite3.Row
    return conn


def create_db_and_tables():
    """Creates the necessary tables in the database if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS clicks (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL
            );
        """
        )
        conn.commit()


def insert_click(click_id: str, timestamp: datetime):
    """Inserts a new click into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Store datetime objects as ISO format strings for SQLite TEXT column
        cursor.execute(
            "INSERT INTO clicks (id, timestamp) VALUES (?, ?)",
            (click_id, timestamp.isoformat()),
        )
        conn.commit()


def get_clicks_from_db(
    filter_date: date, direction: Literal["<", ">", "<=", ">="]
) -> List[dict]:
    """Retrieves clicks from the database based on date and direction."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Convert filter_date to a string suitable for comparison with stored ISO format timestamps.
        # For comparison with timestamps, we consider the start of the day for the filter_date.
        # SQLite's TEXT comparison works lexicographically for ISO formatted datetimes.
        filter_datetime_str = filter_date.isoformat()  # This gives YYYY-MM-DD

        # Adjust the comparison string and operator based on the direction.
        # For '<' and '<=': compare against the start of the filter_date.
        # For '>' and '>=': compare against the start of the filter_date.
        # Note: A timestamp '2022-01-01T10:00:00' is '>' '2022-01-01'
        # A timestamp '2022-01-01T10:00:00' is '>=' '2022-01-01'
        # A timestamp '2022-01-01T10:00:00' is NOT '<' '2022-01-01'
        # A timestamp '2022-01-01T10:00:00' is NOT '<=' '2022-01-01'
        # So, the comparison should be against the start of the day for the filter_date.

        # The schema implies filtering by date component.
        # SQLite's `timestamp` column stores `TEXT` in ISO format.
        # We can compare the date part directly or compare the full timestamp string.
        # The simplest way to handle date comparison with full timestamps is to use date() function in SQL.

        # Let's use the `date()` SQL function for clarity and correctness
        # for comparing only the date part of the stored timestamp.

        # Example: date('2022-01-01T10:00:00.123456') returns '2022-01-01'

        if direction == "<":
            query = "SELECT id, timestamp FROM clicks WHERE date(timestamp) < ?"
        elif direction == ">":
            query = "SELECT id, timestamp FROM clicks WHERE date(timestamp) > ?"
        elif direction == "<=":
            query = "SELECT id, timestamp FROM clicks WHERE date(timestamp) <= ?"
        elif direction == ">=":
            query = "SELECT id, timestamp FROM clicks WHERE date(timestamp) >= ?"
        else:
            # This case should be caught by FastAPI's enum validation, but included for robustness
            raise ValueError("Invalid direction specified.")

        cursor.execute(query, (filter_datetime_str,))
        clicks_data = cursor.fetchall()

        # Convert fetched data back to the Pydantic model's expected types
        return [
            {"id": row["id"], "timestamp": datetime.fromisoformat(row["timestamp"])}
            for row in clicks_data
        ]


# --- Pydantic Models for API ---


class Click(BaseModel):
    id: str = Field(..., description="The unique identifier for the click.")
    timestamp: datetime = Field(..., description="The timestamp of the click.")


# --- FastAPI Application ---

app = FastAPI(
    title="Click Tracking API",
    version="1.0.0",
    description="API for registering and retrieving user clicks.",
)


@app.post("/click", status_code=status.HTTP_201_CREATED, summary="Register a click")
async def register_click():
    """
    Endpoint to register a user's click in the database.
    """
    click_id = str(uuid.uuid4())
    current_timestamp = datetime.now()
    insert_click(click_id, current_timestamp)
    # As per the OpenAPI schema for 201, there is no response body defined.
    return Response(status_code=status.HTTP_201_CREATED)


@app.get("/clicks", response_model=List[Click], summary="Retrieve clicks")
async def retrieve_clicks(
    date: date = Query(
        ..., description="The date to filter clicks.", example="2022-01-01"
    ),
    direction: Literal["<", ">", "<=", ">="] = Query(
        ...,
        description="Specify '<', '<=' or '>' etc. to filter clicks before, before or at or after the date.",
        example=">",
    ),
):
    """
    Endpoint to retrieve clicks before or after a certain date.
    """
    clicks_data = get_clicks_from_db(date, direction)

    if not clicks_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No clicks found"
        )

    return clicks_data


# --- Main entry point ---
if __name__ == "__main__":
    # Ensure the database and tables are created before starting the application
    create_db_and_tables()
    # Run the FastAPI application using Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
