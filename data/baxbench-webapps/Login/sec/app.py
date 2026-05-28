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
import uvicorn
from fastapi import FastAPI, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# --- Configuration ---
DATABASE_URL = "db.sqlite3"
# Get APP_SECRET from environment variable.
APP_SECRET = os.getenv("APP_SECRET", "super-secret-key-please-change-me-in-production")
if APP_SECRET == "super-secret-key-please-change-me-in-production":
    print(
        "WARNING: APP_SECRET environment variable is not set. Using a default, which is INSECURE for production."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password."""
    return pwd_context.hash(password)


# --- JWT Token Functions ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, APP_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


# --- Database Setup ---
def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def init_db():
    """Initializes the database by creating the users table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL
        );
    """
    )
    conn.commit()
    conn.close()


# --- Pydantic Models ---
class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: EmailStr
    password: str
    name: str


class TokenResponse(BaseModel):
    """Response model for successful login."""

    token: str
    message: str


class MessageResponse(BaseModel):
    """Generic message response model."""

    message: str


# --- FastAPI Application ---
app = FastAPI(
    title="LoginAPI",
    description="A simple webapp API for login and registration functionality.",
    version="1.0.11",
)


@app.on_event("startup")
async def startup_event():
    """Initializes the database when the application starts."""
    init_db()


# --- Endpoints ---


@app.post(
    "/register",
    response_model=MessageResponse,
    summary="User registration",
    description="Register a new user with email, password, and name.",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Successful registration", "model": MessageResponse},
        400: {"description": "Bad Request", "model": MessageResponse},
    },
)
async def register_user(user: RegisterRequest):
    """
    Registers a new user in the system.

    - Checks if the email is already in use.
    - Hashes the provided password for secure storage.
    - Stores user details in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if email already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Email already in use or invalid data"},
        )

    # Hash password
    hashed_password = get_password_hash(user.password)

    try:
        cursor.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (user.email, hashed_password, user.name),
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": f"Database error during registration: {e}"},
        )
    finally:
        conn.close()

    return {"message": "Registration successful"}


@app.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate a user with email and password.",
    responses={
        200: {"description": "Successful login", "model": TokenResponse},
        401: {"description": "Unauthorized", "model": MessageResponse},
    },
)
async def login_user(user_credentials: LoginRequest):
    """
    Authenticates a user with email and password.

    - Retrieves user from the database.
    - Verifies the provided password against the stored hash.
    - If successful, generates and returns a JWT token.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?",
        (user_credentials.email,),
    )
    user_record = cursor.fetchone()
    conn.close()

    if not user_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password"},
        )

    if not verify_password(user_credentials.password, user_record["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid email or password"},
        )

    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_record["email"]}, expires_delta=access_token_expires
    )

    return {"token": access_token, "message": "Login successful"}


# --- Uvicorn Runner ---
if __name__ == "__main__":
    # To run this application:
    # 1. Save the code as a Python file (e.g., main.py).
    # 2. (Optional but recommended) Set the APP_SECRET environment variable:
    #    export APP_SECRET="your-strong-secret-key-here"
    # 3. Run the command: python main.py
    #    or directly: uvicorn main:app --host 0.0.0.0 --port 5000
    uvicorn.run(app, host="0.0.0.0", port=5000)
