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
import html
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

# Initialize markdown parser, disabling raw HTML for XSS prevention (CWE-79)
md = MarkdownIt("commonmark").enable("table").disable(["html_block", "html_inline"])

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def init_db():
    """Initializes the database by creating necessary tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
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
                edit_id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                old_content TEXT NOT NULL,
                new_content TEXT NOT NULL,
                modifiedBy TEXT NOT NULL,
                summary TEXT NOT NULL,
                editedAt TEXT NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES entries (id) ON DELETE CASCADE
            );
        """
        )
        conn.commit()
    except sqlite3.Error as e:
        # CWE-703: Log or handle database initialization errors
        print(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()


# Initialize the database when the application starts
init_db()

# --- Pydantic Models ---


class Entry(BaseModel):
    """Represents a wiki entry."""

    id: str
    title: str
    content: str
    lastModifiedBy: str
    lastModifiedAt: datetime


class NewEntry(BaseModel):
    """Model for creating a new wiki entry."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str
    createdBy: str = Field(..., min_length=1, max_length=100)


class UpdateEntry(BaseModel):
    """Model for updating an existing wiki entry."""

    content: str
    modifiedBy: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(..., min_length=1, max_length=255)


# --- FastAPI App ---
app = FastAPI(
    title="Wiki API",
    description="API for a simple wiki where users can add and edit entries, with change tracking.",
    version="1.0.0",
)

# --- Helper Functions for HTML Rendering ---


def render_page_template(title: str, body_content: str) -> str:
    """Basic HTML template for rendering wiki pages."""
    # CWE-79: Escape title when rendering in HTML <title> tag
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} - Wiki</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; margin: 20px; background-color: #f4f4f4; color: #333; }}
        .container {{ max-width: 900px; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #0056b3; }}
        a {{ color: #007bff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        nav {{ margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid #eee; }}
        nav a {{ margin-right: 15px; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ margin-bottom: 10px; }}
        pre {{ background-color: #eee; padding: 10px; border-radius: 5px; overflow-x: auto; }}
        .diff-added {{ background-color: #e6ffed; }}
        .diff-removed {{ background-color: #ffeef0; }}
        .diff-line {{ white-space: pre-wrap; font-family: monospace; padding: 2px 5px; border-radius: 3px; }}
        .diff-header {{ font-weight: bold; margin-top: 15px; }}
        .diff-section {{ border: 1px solid #ddd; padding: 10px; margin-top: 10px; border-radius: 5px; }}
        .contributors {{ margin-top: 20px; border-top: 1px solid #eee; padding-top: 10px; }}
        .contributors h3 {{ margin-bottom: 5px; }}
        .entry-meta {{ font-size: 0.9em; color: #666; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
        .entry-content img {{ max-width: 100%; height: auto; }} /* Responsive images */
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 1em; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="container">
        <nav>
            <a href="/entries">Home</a>
            <a href="/docs">API Docs</a>
        </nav>
        {body_content}
    </div>
</body>
</html>
    """


def generate_diff_html(old_text: str, new_text: str) -> str:
    """Generates an HTML representation of the diff between two texts."""
    d = difflib.Differ()
    # Use splitlines(keepends=True) to preserve newlines for accurate diffing
    diff = d.compare(
        old_text.splitlines(keepends=True), new_text.splitlines(keepends=True)
    )

    diff_html_lines = []
    for line in diff:
        # CWE-79: Escape each line of the diff to prevent XSS
        line_escaped = html.escape(line)
        if line.startswith("+"):
            diff_html_lines.append(
                f'<div class="diff-line diff-added">{line_escaped}</div>'
            )
        elif line.startswith("-"):
            diff_html_lines.append(
                f'<div class="diff-line diff-removed">{line_escaped}</div>'
            )
        else:
            diff_html_lines.append(f'<div class="diff-line">{line_escaped}</div>')
    return "".join(diff_html_lines)


# --- Routes ---


@app.get(
    "/entries",
    summary="Get a list of all entries with their titles and links to respective entries",
    response_class=Response,
)
async def get_all_entries():
    """
    Retrieves a list of all wiki entries and renders them as an HTML page
    with links to each entry.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title FROM entries ORDER BY title;")
        entries_db = cursor.fetchall()
    except sqlite3.Error as e:
        # CWE-703: Catch database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()

    if not entries_db:
        content = "<h1>No wiki entries yet.</h1><p>Create one using the API!</p>"
    else:
        entries_list_html = "<ul>"
        for entry in entries_db:
            # CWE-79: Escape entry ID and title when rendering in HTML
            entries_list_html += f'<li><a href="/entries/{html.escape(entry["id"])}">{html.escape(entry["title"])}</a></li>'
        entries_list_html += "</ul>"
        content = f"<h1>Wiki Entries</h1>{entries_list_html}"

    return Response(
        content=render_page_template("All Entries", content), media_type="text/html"
    )


@app.post(
    "/entries",
    summary="Create a new entry",
    response_model=Entry,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry(new_entry: NewEntry):
    """
    Creates a new wiki entry with the provided title, content, and creator.
    Records the initial creation as an edit.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    try:
        # CWE-89: Use parameterized query to prevent SQL injection
        cursor.execute(
            "INSERT INTO entries (id, title, content, lastModifiedBy, lastModifiedAt) VALUES (?, ?, ?, ?, ?);",
            (entry_id, new_entry.title, new_entry.content, new_entry.createdBy, now),
        )
        # Record the initial creation as an edit
        # CWE-89: Use parameterized query to prevent SQL injection
        cursor.execute(
            "INSERT INTO edits (edit_id, entry_id, old_content, new_content, modifiedBy, summary, editedAt) VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                str(uuid.uuid4()),
                entry_id,
                "",
                new_entry.content,
                new_entry.createdBy,
                "Initial creation",
                now,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        # CWE-703: Handle potential unique constraint violations (though UUID should prevent this for ID)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Entry with this ID already exists (highly unlikely).",
        )
    except sqlite3.Error as e:
        conn.rollback()
        # CWE-703: Catch other database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during entry creation: {e}",
        )
    finally:
        conn.close()

    return Entry(
        id=entry_id,
        title=new_entry.title,
        content=new_entry.content,
        lastModifiedBy=new_entry.createdBy,
        lastModifiedAt=datetime.fromisoformat(now),
    )


@app.get("/entries/{entryId}", summary="Get a specific entry", response_class=Response)
async def get_entry(entryId: str):
    """
    Retrieves a specific wiki entry by its ID, renders its content (markdown),
    last modification details, and lists its contributors as an HTML page.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # CWE-89: Use parameterized query
        cursor.execute("SELECT * FROM entries WHERE id = ?;", (entryId,))
        entry_db = cursor.fetchone()

        if not entry_db:
            # CWE-703: Handle not found case
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
            )

        # Fetch contributors
        # CWE-89: Use parameterized query
        cursor.execute(
            "SELECT DISTINCT modifiedBy FROM edits WHERE entry_id = ? ORDER BY editedAt;",
            (entryId,),
        )
        contributors_db = cursor.fetchall()
        contributors: Set[str] = {row["modifiedBy"] for row in contributors_db}

        # Render markdown content to HTML
        # CWE-79: Markdown-it-py is configured to disable raw HTML,
        # further escaping of the *output* is generally not needed if the parser is safe.
        # But for robustness, we ensure the input to md.render does not contain raw HTML by disabling it.
        rendered_content = md.render(entry_db["content"])

        # CWE-79: Escape title when rendering in HTML
        title_html = html.escape(entry_db["title"])

        # CWE-79: Escape contributor names
        contributors_html = ", ".join(sorted([html.escape(c) for c in contributors]))

        entry_html = f"""
            <h1>{title_html}</h1>
            <div class="entry-meta">
                Last modified by: <strong>{html.escape(entry_db["lastModifiedBy"])}</strong> at {entry_db["lastModifiedAt"]}<br>
                Contributors: {contributors_html}
            </div>
            <div class="entry-content">
                {rendered_content}
            </div>
            <p><a href="/entries/{html.escape(entryId)}/edits">View Edit History</a></p>
        """
        return Response(
            content=render_page_template(entry_db["title"], entry_html),
            media_type="text/html",
        )
    except sqlite3.Error as e:
        # CWE-703: Catch database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()


@app.put("/entries/{entryId}", summary="Update an existing entry", response_model=Entry)
async def update_entry(entryId: str, updated_entry: UpdateEntry):
    """
    Updates an existing wiki entry identified by ID. Records the old and new content
    along with a summary of changes in the edit history.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).isoformat()

    try:
        # First, get the current entry to store its old content
        # CWE-89: Use parameterized query
        cursor.execute("SELECT * FROM entries WHERE id = ?;", (entryId,))
        existing_entry = cursor.fetchone()

        if not existing_entry:
            # CWE-703: Handle not found case
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
            )

        old_content = existing_entry["content"]

        # Update the entry
        # CWE-89: Use parameterized query
        cursor.execute(
            "UPDATE entries SET content = ?, lastModifiedBy = ?, lastModifiedAt = ? WHERE id = ?;",
            (updated_entry.content, updated_entry.modifiedBy, now, entryId),
        )

        # Record the edit
        # CWE-89: Use parameterized query
        cursor.execute(
            "INSERT INTO edits (edit_id, entry_id, old_content, new_content, modifiedBy, summary, editedAt) VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                str(uuid.uuid4()),
                entryId,
                old_content,
                updated_entry.content,
                updated_entry.modifiedBy,
                updated_entry.summary,
                now,
            ),
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        # CWE-703: Catch database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during entry update: {e}",
        )
    finally:
        conn.close()

    return Entry(
        id=entryId,
        title=existing_entry["title"],
        content=updated_entry.content,
        lastModifiedBy=updated_entry.modifiedBy,
        lastModifiedAt=datetime.fromisoformat(now),
    )


@app.get(
    "/entries/{entryId}/edits",
    summary="View the history of edits for a specific entry",
    response_class=Response,
)
async def get_entry_edits(entryId: str):
    """
    Retrieves the full edit history for a specific wiki entry, showing
    contributor, summary, and a diff of content changes for each edit,
    rendered as an HTML page.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if entry exists first
        # CWE-89: Use parameterized query
        cursor.execute("SELECT id, title FROM entries WHERE id = ?;", (entryId,))
        entry_title_row = cursor.fetchone()
        if not entry_title_row:
            # CWE-703: Handle not found case
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
            )

        entry_title = entry_title_row["title"]

        # Get all edits for the entry
        # CWE-89: Use parameterized query
        cursor.execute(
            "SELECT old_content, new_content, modifiedBy, summary, editedAt FROM edits WHERE entry_id = ? ORDER BY editedAt DESC;",
            (entryId,),
        )
        edits_db = cursor.fetchall()

        if not edits_db:
            # CWE-703: Handle case where entry exists but has no edits (unlikely if initial creation is an edit)
            content = f"<h1>Edit History for '{html.escape(entry_title)}'</h1><p>No edit history found for this entry.</p>"
        else:
            edits_html_list = []
            for i, edit in enumerate(edits_db):
                # CWE-79: Escape modifiedBy and summary when rendering in HTML
                modified_by_escaped = html.escape(edit["modifiedBy"])
                summary_escaped = html.escape(edit["summary"])
                edited_at = datetime.fromisoformat(edit["editedAt"]).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )

                diff_output = generate_diff_html(
                    edit["old_content"], edit["new_content"]
                )

                edits_html_list.append(
                    f"""
                    <div class="diff-section">
                        <h3>Edit by {modified_by_escaped} on {edited_at}</h3>
                        <p><strong>Summary:</strong> {summary_escaped}</p>
                        <pre>{diff_output}</pre>
                    </div>
                """
                )
            content = f"<h1>Edit History for '<a href=\"/entries/{html.escape(entryId)}\">{html.escape(entry_title)}</a>'</h1>{''.join(edits_html_list)}"

        return Response(
            content=render_page_template(f"Edit History for {entry_title}", content),
            media_type="text/html",
        )
    except sqlite3.Error as e:
        # CWE-703: Catch database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()


# --- Main entry point for uvicorn ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
