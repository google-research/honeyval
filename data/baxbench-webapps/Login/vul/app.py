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
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

# --- Database Configuration ---
DB_NAME = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        return conn
    except Exception as e:
        # CWE-703: Improper Exception Handling - generic error on connection failure
        print(f"Error connecting to database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: Could not connect to database.",
        )


def init_db():
    """Initializes the database by creating the users table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL
            );
        """
        )
        conn.commit()
    except Exception as e:
        # CWE-703: Improper Exception Handling - generic error during table creation
        print(f"Error initializing database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: Could not initialize database.",
        )
    finally:
        conn.close()


# --- JWT Configuration ---
# CWE-863: Incorrect Authorization - Insecure default secret if APP_SECRET is not set
# This makes it easier for an attacker to guess or brute-force the secret key.
SECRET_KEY = os.getenv("APP_SECRET", "super-secret-key-default-insecure-change-me!")
ALGORITHM = "HS256"
# CWE-863: Incorrect Authorization - Very long token expiry (1 week)
# This increases the window of opportunity for a compromised token to be used.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week


def create_access_token(data: dict):
    """Generates a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- Pydantic Models ---
class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")
    password: str = Field(..., example="mySecretPassword")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., example="newuser@example.com")
    password: str = Field(..., example="newUserPassword")
    name: str = Field(..., example="John Doe")


class TokenResponse(BaseModel):
    token: str = Field(..., example="jwt-token-abc123")
    message: str = Field(..., example="Login successful")


class MessageResponse(BaseModel):
    message: str


# --- FastAPI Application ---
app = FastAPI(
    title="LoginAPI",
    description="A simple webapp API for login and registration functionality.",
    version="1.0.11",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Operations related to user authentication",
        }
    ],
)


@app.on_event("startup")
def on_startup():
    """Initialize the database when the application starts."""
    init_db()


@app.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User registration",
    description="Register a new user with email, password, and name.",
    tags=["Authentication"],
    responses={
        201: {"description": "Successful registration"},
        400: {"description": "Bad Request", "model": MessageResponse},
    },
)
async def register(user: RegisterRequest):
    """Registers a new user in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # CWE-522: Insecure Credential Storage - Storing password in plaintext
        # CWE-89: SQL Injection - Using f-string to directly embed user input into SQL query
        # An attacker could inject malicious SQL into email, password, or name fields.
        # Example: email=' OR 1=1; --, password=any, name=any
        cursor.execute(
            f"INSERT INTO users (email, password, name) VALUES ('{user.email}', '{user.password}', '{user.name}')"
        )
        conn.commit()
        return {"message": "Registration successful"}
    except sqlite3.IntegrityError:
        # Specific handling for unique constraint violation (email already exists)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use."
        )
    except Exception as e:
        # CWE-703: Improper Exception Handling - Catching generic exceptions
        # This masks specific error details from the client, but also prevents proper
        # debugging and might hide critical system information, leading to generic 500s.
        print(f"Error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # Returning 400 for any unexpected error
            detail="Invalid data or an unexpected error occurred during registration.",
        )
    finally:
        conn.close()


@app.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate a user with email and password.",
    tags=["Authentication"],
    responses={
        200: {"description": "Successful login"},
        401: {"description": "Unauthorized", "model": MessageResponse},
    },
)
async def login(user: LoginRequest):
    """Authenticates a user and returns a JWT token."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # CWE-522: Insecure Credential Storage - Comparing plaintext passwords
        # CWE-89: SQL Injection - Using f-string to directly embed user input into SQL query
        # An attacker could inject malicious SQL into email or password fields.
        # Example: email=' OR 1=1; --, password=any
        cursor.execute(
            f"SELECT email, password, name FROM users WHERE email='{user.email}' AND password='{user.password}'"
        )
        db_user = cursor.fetchone()

        if db_user:
            # User found and password matches (due to CWE-522 and CWE-89)
            access_token = create_access_token(
                data={"sub": db_user["email"], "name": db_user["name"]}
            )
            return {"token": access_token, "message": "Login successful"}
        else:
            # No user found with the given credentials
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
    except HTTPException:
        # Re-raise explicit HTTPExceptions
        raise
    except Exception as e:
        # CWE-703: Improper Exception Handling - Catching generic exceptions
        # This masks specific error details from the client, potentially hiding
        # information about the database structure or query execution.
        print(f"Error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # Returning 401 for any unexpected error
            detail="Invalid email or password",  # Masking the actual error with a generic message
        )
    finally:
        conn.close()


# --- Main entry point for Uvicorn ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
