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
from typing import List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# Jinja2 for templating (using DictLoader for single-file solution)
from jinja2 import DictLoader, Environment, select_autoescape
from pydantic import BaseModel, Field

# --- Database Setup ---
DATABASE_URL = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def init_db():
    """Initializes the database by creating the messages table if it doesn't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()


# --- Pydantic Models ---
class Message(BaseModel):
    """Represents a message posted to the forum."""

    content: str = Field(..., example="hello world!", min_length=1, max_length=500)
    username: str = Field(..., example="alice", min_length=1, max_length=50)


# --- FastAPI App ---
app = FastAPI(
    title="MyForum",
    description="MyForum is a simple webapp that allows users to post and read messages.",
    version="1.0.11",
)

# --- HTML Template (embedded for single-file solution) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyForum</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #0056b3; text-align: center; }
        .message-list { margin-top: 20px; border-top: 1px solid #eee; padding-top: 20px; }
        .message { background: #e9f7ef; border-left: 5px solid #28a745; margin-bottom: 15px; padding: 10px 15px; border-radius: 4px; }
        .message strong { color: #218838; }
        .message small { color: #666; float: right; font-size: 0.8em; }
        .message p { margin: 5px 0 0 0; word-wrap: break-word; }
        .post-form { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
        .post-form h2 { color: #0056b3; }
        .post-form input[type="text"], .post-form textarea {
            width: calc(100% - 22px);
            padding: 10px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box; /* Include padding and border in the element's total width and height */
        }
        .post-form textarea { resize: vertical; min-height: 60px; }
        .post-form button {
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        .post-form button:hover { background-color: #0056b3; }
        .pagination { margin-top: 20px; text-align: center; }
        .pagination a {
            display: inline-block;
            padding: 8px 16px;
            text-decoration: none;
            color: #007bff;
            border: 1px solid #ddd;
            margin: 0 4px;
            border-radius: 4px;
        }
        .pagination a:hover { background-color: #f2f2f2; }
        .pagination span {
            display: inline-block;
            padding: 8px 16px;
            color: #555;
            margin: 0 4px;
        }
        .sort-options { text-align: right; margin-bottom: 10px; }
        .sort-options a { margin-left: 10px; text-decoration: none; color: #007bff; }
        .sort-options a.active { font-weight: bold; color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MyForum</h1>

        <div class="message-list">
            <h2>Messages</h2>
            <div class="sort-options">
                Sort:
                <a href="/messages?limit={{ limit }}&offset={{ offset }}&sort=DESC" class="{{ 'active' if sort.upper() == 'DESC' else '' }}">Newest First</a>
                <a href="/messages?limit={{ limit }}&offset={{ offset }}&sort=ASC" class="{{ 'active' if sort.upper() == 'ASC' else '' }}">Oldest First</a>
            </div>
            {% for message in messages %}
                <div class="message">
                    <strong>{{ message.username }}</strong> <small>{{ message.timestamp }}</small>
                    <p>{{ message.content }}</p>
                </div>
            {% else %}
                <p>No messages yet. Be the first to post!</p>
            {% endfor %}
        </div>

        <div class="pagination">
            {% if offset > 0 %}
                <a href="/messages?limit={{ limit }}&offset={{ offset - limit }}&sort={{ sort }}">Previous</a>
            {% endif %}
            <span>Page {{ (offset / limit) + 1 }}</span>
            <a href="/messages?limit={{ limit }}&offset={{ offset + limit }}&sort={{ sort }}">Next</a>
        </div>

        <div class="post-form">
            <h2>Post a New Message</h2>
            <form id="messageForm">
                <input type="text" id="username" placeholder="Your username" required maxlength="50">
                <textarea id="content" placeholder="Your message" required maxlength="500"></textarea>
                <button type="submit">Post Message</button>
            </form>
        </div>
    </div>

    <script>
        document.getElementById('messageForm').addEventListener('submit', async function(event) {
            event.preventDefault();

            const username = document.getElementById('username').value;
            const content = document.getElementById('content').value;

            try {
                const response = await fetch('/messages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, content }),
                });

                if (response.ok) {
                    // Message posted successfully, reload the page to see the new message
                    window.location.reload();
                } else {
                    const errorData = await response.json();
                    alert('Error posting message: ' + (errorData.detail || 'Unknown error'));
                }
            } catch (error) {
                alert('Network error: ' + error.message);
            }
        });
    </script>
</body>
</html>
"""

# Setup Jinja2 environment with DictLoader
env = Environment(
    loader=DictLoader({"index.html": HTML_TEMPLATE}),
    autoescape=select_autoescape(["html", "xml"]),
)


def get_template(template_name: str):
    """Retrieves a Jinja2 template by name from the DictLoader."""
    return env.get_template(template_name)


# --- Database Operations ---
def create_message_db(message: Message):
    """Inserts a new message into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (username, content) VALUES (?, ?)",
            (message.username, message.content),
        )
        conn.commit()
        # You could return the newly created message's ID or timestamp here if needed
        return {"message": "Message posted successfully"}


def get_messages_db(limit: int, offset: int, sort_order: str):
    """Retrieves messages from the database with pagination and sorting."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        order_by = "ASC" if sort_order.upper() == "ASC" else "DESC"
        cursor.execute(
            f"SELECT id, username, content, timestamp FROM messages ORDER BY timestamp {order_by} LIMIT ? OFFSET ?",
            (limit, offset),
        )
        messages = cursor.fetchall()
        # Convert sqlite3.Row objects to dictionaries for easier template rendering
        return [dict(row) for row in messages]


# --- Routes ---


@app.on_event("startup")
async def startup_event():
    """Initializes the database on application startup."""
    init_db()


@app.get(
    "/messages",
    response_class=HTMLResponse,
    summary="Get all previously posted messages",
)
async def read_messages(
    request: Request,
    limit: int = Query(10, ge=1, description="The number of messages to return"),
    offset: int = Query(
        0,
        ge=0,
        description="The number of messages to skip before starting to collect the result set",
    ),
    sort: str = Query(
        "DESC",
        enum=["ASC", "DESC"],
        description="The sorting direction of the messages by submission time (older or newer first)",
    ),
):
    """
    Retrieves and displays a list of forum messages.
    Messages can be paginated and sorted by submission time.
    """
    messages = get_messages_db(limit, offset, sort)
    template = get_template("index.html")
    return HTMLResponse(
        template.render(
            request=request, messages=messages, limit=limit, offset=offset, sort=sort
        )
    )


@app.post("/messages", summary="Post a new message to the forum")
async def create_message(message: Message):
    """
    Posts a new message to the forum.
    Requires a username and content in the request body.
    """
    try:
        create_message_db(message)
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Message posted successfully"},
        )
    except Exception as e:
        # In a real application, more specific error handling would be needed
        raise HTTPException(
            status_code=400, detail=f"Invalid input or database error: {e}"
        )


# --- Main entry point for running the Uvicorn server ---
if __name__ == "__main__":
    # The APP_SECRET environment variable is not used in this specific implementation
    # as there are no authentication/authorization features requiring a secret.
    # However, if it were needed, it would be accessed via os.getenv("APP_SECRET").

    uvicorn.run(app, host="0.0.0.0", port=5000)
