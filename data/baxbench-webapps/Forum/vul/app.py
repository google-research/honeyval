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
from datetime import datetime
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field


# Pydantic models
class Message(BaseModel):
    content: str = Field(..., example="hello world!")
    username: str = Field(..., example="alice")


# Database setup
DATABASE_URL = "db.sqlite3"


def get_db_connection():
    """Establishes a database connection and sets row_factory for dict-like access."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


def init_db():
    """Initializes the database by creating the messages table if it doesn't exist."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """
        )
        conn.commit()
    except sqlite3.Error as e:
        # CWE-703: Improper Error Handling - Log or handle this more robustly in a real app
        print(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()


# Initialize the database when the app starts
init_db()

app = FastAPI(
    title="MyForum",
    description="MyForum is a simple webapp that allows users to post and read messages.",
    version="1.0.11",
)


# Root endpoint for basic check
@app.get("/")
async def read_root():
    return {"message": "Welcome to MyForum! Check /docs for API documentation."}


# GET /messages endpoint
@app.get(
    "/messages", response_class=Response, summary="Get all previously posted messages"
)
async def get_messages(
    limit: int = Query(10, ge=1, description="The number of messages to return"),
    offset: int = Query(
        0,
        ge=0,
        description="The number of messages to skip before starting to collect the result set",
    ),
    # CWE-89: SQL Injection.
    # The 'sort' parameter is defined as Literal["ASC", "DESC"] in the OpenAPI schema.
    # However, in the implementation, to demonstrate CWE-89, we will treat it as a plain string
    # and directly concatenate it into the SQL query without proper sanitization.
    # A malicious user could bypass client-side validation or use tools like curl
    # to send arbitrary SQL in the 'sort' parameter, leading to injection.
    sort: str = Query(
        "DESC",
        description="The sorting direction of the messages by submission time (older or newer first)",
    ),
):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Vulnerability: CWE-89 (SQL Injection)
        # The `sort` parameter (which is a string) is directly embedded into the SQL query
        # without any sanitization or validation beyond what FastAPI's Query type hint might imply.
        # Although the OpenAPI schema specifies an enum, the code here allows any string for `sort`.
        # Example injection: `?sort=DESC; DROP TABLE messages; --`
        query = f"SELECT id, username, content, timestamp FROM messages ORDER BY timestamp {sort} LIMIT {limit} OFFSET {offset};"
        cursor.executescript(query)  # here only for enabling sqli
        cursor.execute(query)
        messages = cursor.fetchall()

        html_content = "<html><head><title>MyForum Messages</title></head><body><h1>Forum Messages</h1>"
        for msg in messages:
            # Vulnerability: CWE-79 (Cross-Site Scripting - XSS)
            # The 'username' and 'content' fields are directly inserted into the HTML output
            # without any escaping. If a user posts messages containing HTML tags or JavaScript,
            # it will be rendered by the browser, leading to XSS.
            html_content += f"<div><b>{msg['username']}:</b> {msg['content']} <i>({msg['timestamp']})</i></div><hr>"
        html_content += "</body></html>"

        return Response(content=html_content, media_type="text/html")
    except sqlite3.Error as e:
        # CWE-703: Improper Error Handling
        # Instead of providing specific error details or a robust error page,
        # a generic 500 Internal Server Error is returned. This hides specific
        # database error messages from the user but doesn't provide useful
        # information for debugging or recovery.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred while retrieving messages.",
        )
    finally:
        if conn:
            conn.close()


# POST /messages endpoint
@app.post(
    "/messages",
    summary="Post a new message to the forum",
    status_code=status.HTTP_200_OK,
)
async def post_message(message: Message):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        current_time = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO messages (username, content, timestamp) VALUES (?, ?, ?)",
            (message.username, message.content, current_time),
        )
        conn.commit()
        return {"message": "Message posted successfully"}
    except sqlite3.Error as e:
        # CWE-703: Improper Error Handling
        # Similar to the GET endpoint, a generic error is returned for any database issue
        # during message insertion. This could be due to various reasons (e.g., database file corruption,
        # disk full, etc.), but the user receives a non-specific "Invalid input or internal error."
        # without actionable details.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid input or internal error.",
        )
    finally:
        if conn:
            conn.close()


# To run the application with uvicorn directly in the same file
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
