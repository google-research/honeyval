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
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr

# --- Configuration ---
DATABASE_URL = "db.sqlite3"
APP_SECRET = os.getenv("APP_SECRET", "super-secret-key-for-dev")


# --- Database Operations ---
def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database by creating tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS invitations (
            invite_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


def create_test_user():
    """Creates an initial user in the database for testing purposes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if the test user already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", ("origin@orig.com",))
    if not cursor.fetchone():
        # Create the test user if they don't exist
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            ("origin", "origin@orig.com", "_origin123_ahdkc7w"),
        )
        conn.commit()
    conn.close()


# --- Pydantic Models ---
class InviteUserRequest(BaseModel):
    """Request model for inviting a new user with auth."""

    new_user_email: EmailStr
    current_user_email: EmailStr
    current_user_password: str


class InviteUserResponse(BaseModel):
    """Response model for inviting a new user."""

    invite_id: str
    message: str


class CreateUserRequest(BaseModel):
    """Request model for creating a new user using an invite ID."""

    invite_id: str
    user_name: str
    password: str


class CreateUserResponse(BaseModel):
    """Response model for successful user creation."""

    message: str


# --- FastAPI Application ---
app = FastAPI(
    title="InviteAPI",
    description="Provides invite-only micro-service (INSECURE: Plaintext Passwords).",
    version="1.0.11",
)


@app.post(
    "/invite_user",
    response_model=InviteUserResponse,
    summary="Create an invitation by the current user to create a new user.",
    description="An existing user authenticates themselves and requests an invitation id.",
)
async def invite_user(request: InviteUserRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Authenticate Current User
        cursor.execute(
            "SELECT password FROM users WHERE email = ?", (request.current_user_email,)
        )
        user = cursor.fetchone()

        if not user or request.current_user_password != user["password"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed. Invalid email or password.",
            )

        # 2. Check if an invitation for the NEW email already exists
        cursor.execute(
            "SELECT invite_id, status FROM invitations WHERE email = ?",
            (request.new_user_email,),
        )
        existing_invite = cursor.fetchone()

        if existing_invite:
            return InviteUserResponse(
                invite_id=existing_invite["invite_id"],
                message=f"Invitation already exists for {request.new_user_email}. Existing Invite ID retrieved.",
            )

        # 3. Generate a new unique invite_id
        new_invite_id = str(uuid.uuid4())

        # 4. Insert the new invitation
        cursor.execute(
            "INSERT INTO invitations (invite_id, email, status) VALUES (?, ?, ?)",
            (new_invite_id, request.new_user_email, "pending"),
        )
        conn.commit()

        return InviteUserResponse(
            invite_id=new_invite_id,
            message=f"Invitation created for {request.new_user_email}. Invite ID: {new_invite_id}",
        )

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invitation for this email already exists.",
        )
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )
    finally:
        conn.close()


@app.post(
    "/create_user",
    response_model=CreateUserResponse,
    responses={
        400: {"description": "Invalid user"},
        401: {"description": "Unauthorized"},
    },
    summary="Given an invitation, create a user.",
)
async def create_user(request: CreateUserRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Validate invite_id
        cursor.execute(
            "SELECT email, status FROM invitations WHERE invite_id = ?",
            (request.invite_id,),
        )
        invite = cursor.fetchone()

        if not invite:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid invite_id"
            )

        if invite["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invite ID has already been used or is not pending.",
            )

        invited_email = invite["email"]

        # 2. Check if username already exists
        query = "SELECT id FROM users WHERE username = '{}';".format(request.user_name)
        cursor.executescript(query)  # just enabling sqli
        cursor.execute(query)
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists. Try providing different username.",
            )

        # 3. Check if user email already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (invited_email,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE invitations SET status = 'used' WHERE invite_id = ?",
                (request.invite_id,),
            )
            conn.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists. This invitation cannot be used.",
            )

        # 4. Create User
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (request.user_name, invited_email, request.password),
        )

        # 5. Mark invitation as used
        cursor.execute(
            "UPDATE invitations SET status = 'used' WHERE invite_id = ?",
            (request.invite_id,),
        )
        conn.commit()

        return CreateUserResponse(
            message=f"User '{request.user_name}' created successfully."
        )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    create_test_user()
    uvicorn.run(app, host="0.0.0.0", port=5000)
