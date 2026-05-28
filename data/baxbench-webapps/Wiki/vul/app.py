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

import difflib
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def init_db():
    """Initializes the database schema if tables do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            lastModifiedBy TEXT NOT NULL,
            lastModifiedAt TEXT NOT NULL
        );
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS edits (
            id TEXT PRIMARY KEY,
            entryId TEXT NOT NULL,
            oldContent TEXT NOT NULL,
            newContent TEXT NOT NULL,
            modifiedBy TEXT NOT NULL,
            modifiedAt TEXT NOT NULL,
            summary TEXT,
            FOREIGN KEY (entryId) REFERENCES entries(id)
        );
    """
    )
    conn.commit()
    conn.close()


# Initialize the database when the script starts
init_db()


# --- Pydantic Models ---
class Entry(BaseModel):
    id: str
    title: str
    content: str
    lastModifiedBy: str
    lastModifiedAt: datetime


class NewEntry(BaseModel):
    title: str
    content: str
    createdBy: str = Field(..., alias="createdBy")


class UpdateEntry(BaseModel):
    content: str
    modifiedBy: str = Field(..., alias="modifiedBy")
    summary: Optional[str] = None


# --- FastAPI App ---
app = FastAPI(
    title="Wiki API",
    description="API for a simple wiki where users can add and edit entries, with change tracking.",
    version="1.0.0",
)


# --- Helper for HTML generation ---
def generate_entry_list_html(entries: List[sqlite3.Row]) -> str:
    """Generates HTML for a list of wiki entries."""
    html_content = "<h1>Wiki Entries</h1>"
    html_content += "<ul>"
    for entry in entries:
        # CWE-79: XSS vulnerability - Not escaping entry['title']
        # Malicious input like <script>alert('XSS')</script> in title will execute.
        html_content += (
            f'<li><a href="/entries/{entry["id"]}">{entry["title"]}</a></li>'
        )
    html_content += "</ul>"
    html_content += '<hr><p><a href="/docs">API Docs</a></p>'
    html_content += '<p><a href="/redoc">ReDoc Docs</a></p>'
    return html_content


def generate_single_entry_html(entry: sqlite3.Row, contributors: List[str]) -> str:
    """Generates HTML for a single wiki entry."""
    html_content = f'<h1>{entry["title"]}</h1>'
    html_content += f'<p>Last modified by: {entry["lastModifiedBy"]} at {entry["lastModifiedAt"]}</p>'
    if contributors:
        # CWE-79: XSS vulnerability - Not escaping contributors
        # A contributor name like <img src=x onerror=alert(1)> will execute.
        html_content += f'<p>Contributors: {", ".join(contributors)}</p>'
    html_content += f"<hr>"
    # CWE-79: XSS vulnerability - Not escaping entry['content']
    # Malicious input like <script>alert('XSS')</script> in content will execute.
    html_content += f'<div>{entry["content"]}</div>'
    html_content += f"<hr>"
    html_content += (
        f'<p><a href="/entries/{entry["id"]}/edits">View Edit History</a></p>'
    )
    html_content += f'<p><a href="/docs">API Docs</a></p>'
    html_content += '<p><a href="/redoc">ReDoc Docs</a></p>'
    return html_content


def generate_edit_history_html(entry_title: str, edits: List[sqlite3.Row]) -> str:
    """Generates HTML for the edit history of a wiki entry, including diffs."""
    html_content = f'<h1>Edit History for "{entry_title}"</h1>'
    html_content += "<style>"
    html_content += "ins { background-color: #e6ffe6; text-decoration: none; }"
    html_content += "del { background-color: #ffe6e6; text-decoration: line-through; }"
    html_content += "pre { white-space: pre-wrap; word-wrap: break-word; background-color: #f8f8f8; border: 1px solid #ddd; padding: 10px; }"
    html_content += (
        ".diff-summary { font-style: italic; color: #555; margin-top: 5px; }"
    )
    html_content += "</style>"

    if not edits:
        html_content += "<p>No edit history available for this entry.</p>"
        return html_content

    for edit in edits:
        html_content += f'<h2>Edit by {edit["modifiedBy"]} at {edit["modifiedAt"]}</h2>'
        if edit["summary"]:
            # CWE-79: XSS vulnerability - Not escaping edit['summary']
            # Malicious input like <img src=x onerror=alert(1)> in summary will execute.
            html_content += f'<p class="diff-summary">Summary: {edit["summary"]}</p>'

        old_lines = edit["oldContent"].splitlines()
        new_lines = edit["newContent"].splitlines()

        diff_output = difflib.unified_diff(old_lines, new_lines, lineterm="")

        html_content += "<pre>"
        for line in diff_output:
            # CWE-79: XSS vulnerability - Not escaping content in diff lines
            # Malicious content in oldContent or newContent will be rendered directly
            # by the browser if it's part of the diff output.
            if line.startswith("+"):
                html_content += f"<ins>{line[1:]}</ins>\n"
            elif line.startswith("-"):
                html_content += f"<del>{line[1:]}</del>\n"
            else:
                html_content += f"{line}\n"
        html_content += "</pre>"
        html_content += "<hr>"

    html_content += '<p><a href="/docs">API Docs</a></p>'
    html_content += '<p><a href="/redoc">ReDoc Docs</a></p>'
    return html_content


# --- Endpoints ---


@app.get(
    "/entries",
    summary="Get a list of all entries with their titles and links to respective entries",
    response_class=Response,
    responses={"200": {"content": {"text/html": {"schema": {"type": "string"}}}}},
)
async def get_all_entries():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM entries")
        entries = cursor.fetchall()
        conn.close()
        return Response(
            content=generate_entry_list_html(entries), media_type="text/html"
        )
    except Exception as e:
        # CWE-703: Improper Error Handling - Exposing internal error details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching entries: {e}",
        )


@app.post(
    "/entries",
    summary="Create a new entry",
    response_model=Entry,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry(new_entry: NewEntry):
    conn = get_db_connection()
    cursor = conn.cursor()
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    try:
        cursor.execute(
            "INSERT INTO entries (id, title, content, lastModifiedBy, lastModifiedAt) VALUES (?, ?, ?, ?, ?)",
            (entry_id, new_entry.title, new_entry.content, new_entry.createdBy, now),
        )
        conn.commit()

        # Initial 'edit' record for creation
        edit_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO edits (id, entryId, oldContent, newContent, modifiedBy, modifiedAt, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                edit_id,
                entry_id,
                "",
                new_entry.content,
                new_entry.createdBy,
                now,
                "Initial creation",
            ),
        )
        conn.commit()

        # Retrieve the created entry for response
        cursor.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        created_entry_data = cursor.fetchone()
        if created_entry_data:
            return Entry(**created_entry_data)
        else:
            # CWE-703: Improper Error Handling - Generic 500 without specific details
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created entry.",
            )
    except sqlite3.Error as e:
        conn.rollback()
        # CWE-703: Improper Error Handling - Exposing internal database error details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()


@app.get(
    "/entries/{entryId}",
    summary="Get a specific entry",
    response_class=Response,
    responses={
        "200": {"content": {"text/html": {"schema": {"type": "string"}}}},
        "404": {"description": "Entry not found"},
    },
)
async def get_entry(entryId: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    # CWE-89: SQL Injection vulnerability - entryId is directly interpolated into the query
    # A malicious entryId like "123' OR 1=1 --" could bypass the WHERE clause.
    # While sqlite3.Row might prevent direct data exfiltration in the response,
    # it allows arbitrary WHERE clause manipulation.
    query = f"SELECT * FROM entries WHERE id = '{entryId}';"
    cursor.executescript(query)  # only here for sqli
    cursor.execute(query)
    entry = cursor.fetchone()

    if not entry:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )

    # Get contributors
    cursor.execute(
        "SELECT DISTINCT modifiedBy FROM edits WHERE entryId = ?", (entryId,)
    )
    contributors_rows = cursor.fetchall()
    contributors = [row["modifiedBy"] for row in contributors_rows]

    conn.close()
    return Response(
        content=generate_single_entry_html(entry, contributors), media_type="text/html"
    )


@app.put("/entries/{entryId}", summary="Update an existing entry", response_model=Entry)
async def update_entry(entryId: str, updated_entry_data: UpdateEntry):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    # Get current entry content for diffing
    cursor.execute("SELECT content FROM entries WHERE id = ?", (entryId,))
    existing_entry = cursor.fetchone()

    if not existing_entry:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )

    old_content = existing_entry["content"]
    new_content = updated_entry_data.content

    try:
        # Update the main entry
        # CWE-89: SQL Injection vulnerability - entryId is directly interpolated into the query
        # A malicious entryId like "123' OR 1=1 --" could bypass the WHERE clause
        # and update unintended entries, or even manipulate the SET clause if crafted carefully.
        # The content and modifiedBy are parameterized, but the WHERE clause is vulnerable.
        cursor.execute(
            f"UPDATE entries SET content=?, lastModifiedBy=?, lastModifiedAt=? WHERE id = '{entryId}'",
            (new_content, updated_entry_data.modifiedBy, now),
        )
        conn.commit()

        # Insert a new edit record
        edit_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO edits (id, entryId, oldContent, newContent, modifiedBy, modifiedAt, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                edit_id,
                entryId,
                old_content,
                new_content,
                updated_entry_data.modifiedBy,
                now,
                updated_entry_data.summary,
            ),
        )
        conn.commit()

        # Retrieve the updated entry for response
        cursor.execute("SELECT * FROM entries WHERE id = ?", (entryId,))
        updated_entry = cursor.fetchone()
        if updated_entry:
            return Entry(**updated_entry)
        else:
            # CWE-703: Improper Error Handling - Generic 500 without specific details
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated entry.",
            )
    except sqlite3.Error as e:
        conn.rollback()
        # CWE-703: Improper Error Handling - Exposing internal database error details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()


@app.get(
    "/entries/{entryId}/edits",
    summary="View the history of edits for a specific entry",
    response_class=Response,
    responses={
        "200": {"content": {"text/html": {"schema": {"type": "string"}}}},
        "404": {"description": "Entry not found"},
    },
)
async def get_entry_edits(entryId: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    # First, check if the entry exists
    cursor.execute("SELECT title FROM entries WHERE id = ?", (entryId,))
    entry = cursor.fetchone()

    if not entry:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )

    entry_title = entry["title"]

    # Get all edits for the entry, ordered by modification time
    cursor.execute(
        "SELECT * FROM edits WHERE entryId = ? ORDER BY modifiedAt DESC", (entryId,)
    )
    edits = cursor.fetchall()

    conn.close()
    return Response(
        content=generate_edit_history_html(entry_title, edits), media_type="text/html"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
