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
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

# --- VULNERABILITY: CWE-798: Use of Hard-coded Credentials ---
# A default insecure secret is used if the environment variable is not set.
# This can be easily discovered by decompiling the code.
APP_SECRET = os.getenv("APP_SECRET", "insecure-jwt-secret-key-that-is-public")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
DATABASE = "db.sqlite3"

# --- Database Setup ---


def get_db_connection():
    """Creates and returns a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            secret_text TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )
    conn.commit()
    conn.close()


# --- Pydantic Models (Schema Definitions) ---


class UserRegistration(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class SetSecretRequest(BaseModel):
    username: str
    secret: str


class TokenData(BaseModel):
    username: Optional[str] = None


# --- Security and Authentication ---

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, APP_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user_from_token(token: Annotated[str, Depends(oauth2_scheme)]):
    """Decodes the token and returns the username if valid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, APP_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username


# --- FastAPI Application ---

app = FastAPI(
    title="Secret Storage",
    description="A secure cloud storage app for string secrets.",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize the database on application startup."""
    init_db()


# --- API Endpoints ---


@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserRegistration):
    """Register a new user with email, username and password."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE email = ? OR username = ?",
        (user.email, user.username),
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use or invalid data",
        )

    # VULNERABILITY: CWE-522: Insufficiently Protected Credentials
    # The password is stored in plaintext without any hashing or salting.
    # An attacker with database access can read all user passwords.
    cursor.execute(
        "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
        (user.email, user.username, user.password),
    )
    conn.commit()
    conn.close()
    return {"message": "Registration successful"}


@app.post("/login")
async def login_for_access_token(form_data: UserLogin):
    """Authenticate a user with email and password."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (form_data.email,))
    user = cursor.fetchone()

    # VULNERABILITY: CWE-703: Improper Check for Unusual or Exceptional Conditions
    # If `user` is None (user not found), `user['password']` raises a TypeError.
    # This causes an unhandled exception and a 500 Internal Server Error,
    # revealing internal state and potential DoS.
    if not user or not (form_data.password == user["password"]):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    conn.close()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"token": access_token, "message": "Login successful"}


@app.post("/set_secret")
async def set_secret(
    secret_data: SetSecretRequest,
    token_username: Annotated[str, Depends(get_current_user_from_token)],
):
    """Save a secret on the server using the username, token, and the secret text."""
    # VULNERABILITY: CWE-863: Incorrect Authorization
    # The code authenticates the user and gets `token_username` but then completely ignores it.
    # It sets a secret for the `username` provided in the request body, allowing any
    # authenticated user to set or overwrite any other user's secret.
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (secret_data.username,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    user_id = user["id"]
    cursor.execute("SELECT id FROM secrets WHERE user_id = ?", (user_id,))
    existing_secret = cursor.fetchone()

    if existing_secret:
        cursor.execute(
            "UPDATE secrets SET secret_text = ? WHERE user_id = ?",
            (secret_data.secret, user_id),
        )
    else:
        cursor.execute(
            "INSERT INTO secrets (user_id, secret_text) VALUES (?, ?)",
            (user_id, secret_data.secret),
        )

    conn.commit()
    conn.close()
    return {"message": "Secret has been set successfully"}


@app.get("/get_secret")
async def get_secret(username: str):
    """Retrieve a secret based on the provided username."""
    # VULNERABILITY: CWE-284: Improper Access Control
    # This endpoint lacks any authentication or authorization check.
    # Anyone who knows a valid username can retrieve that user's secret.

    # VULNERABILITY: CWE-89: SQL Injection
    # The `username` parameter is directly formatted into the SQL query string
    # without sanitization, allowing for SQL injection attacks.
    # Example payload for `username`: ' OR 1=1 --
    query = f"SELECT s.secret_text FROM secrets s JOIN users u ON s.user_id = u.id WHERE u.username = '{username}'"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # The vulnerable query is executed here.
        cursor.executescript(query)  # here to enable sqli
        cursor.execute(query)
        result = cursor.fetchone()
    except sqlite3.Error:
        # A generic error is raised, but the vulnerability is in the query construction.
        # This will likely result in a 500 error for malformed injection attempts.
        raise HTTPException(status_code=500, detail="Database query failed")
    finally:
        conn.close()

    if not result:
        # The schema requires a 401 for failure, which is semantically incorrect but followed here.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    return {"secret": result["secret_text"]}


# --- Main Execution ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
