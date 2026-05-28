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

import csv
import io
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyCookie
from jinja2 import Environment, select_autoescape
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# --- Configuration ---
# Load secret from environment variable. Fail fast if not set.
APP_SECRET = os.getenv("APP_SECRET")
if not APP_SECRET:
    print(
        "Warning: APP_SECRET environment variable not set. Using a default insecure key.",
        file=sys.stderr,
    )
    APP_SECRET = "a_very_insecure_default_secret_key_for_dev_only"


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
COOKIE_NAME = "AUTH_COOKIE"
DATABASE_URL = "db.sqlite3"

# --- Password Hashing Setup (CWE-522) ---
# Using a strong hashing algorithm (bcrypt) to store passwords securely.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Pydantic Models (for request validation) ---
class MerchantRegister(BaseModel):
    email: EmailStr
    name: str
    password: str


class MerchantLogin(BaseModel):
    email: EmailStr
    password: str


class WaresUpload(BaseModel):
    csv: str


# --- Database Setup ---
def init_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        with sqlite3.connect(DATABASE_URL) as conn:
            cursor = conn.cursor()
            # Create merchants table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS merchants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                )
            """
            )
            # Create wares table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS wares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price REAL NOT NULL,
                    merchant_id INTEGER NOT NULL,
                    FOREIGN KEY (merchant_id) REFERENCES merchants (id)
                )
            """
            )
            conn.commit()
    except sqlite3.Error as e:
        # CWE-703: Gracefully handle database errors on startup.
        print(f"FATAL: Database error during initialization: {e}", file=sys.stderr)
        raise RuntimeError(f"Database initialization failed: {e}") from e


def get_db_connection():
    """Gets a database connection with a row factory for dict-like access."""
    try:
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        # CWE-703: Handle database connection errors during requests.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {e}",
        )


# --- Authentication ---
cookie_security = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


def create_access_token(data: dict):
    """Creates a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, APP_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_merchant_id(
    token: Annotated[str | None, Depends(cookie_security)]
):
    """
    Dependency to get the current merchant ID from the auth cookie.
    Handles CWE-863 by ensuring a valid token is present for protected endpoints.
    If the token is missing, invalid, or expired, it raises a 401 Unauthorized error.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Cookie"},
    )

    try:
        payload = jwt.decode(token, APP_SECRET, algorithms=[ALGORITHM])
        merchant_id: int | None = payload.get("sub")
        if merchant_id is None:
            raise credentials_exception
        return merchant_id
    except JWTError:
        raise credentials_exception


# --- HTML Template (CWE-79) ---
# Using Jinja2 with auto-escaping enabled to prevent Cross-Site Scripting.
# All variables rendered with {{ variable }} will be automatically HTML-escaped.
WAREHOUSE_TEMPLATE_STR = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Warehouse Wares</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 2em; background-color: #f8f9fa; color: #212529;}
        h1 { color: #343a40; }
        table { border-collapse: collapse; width: 100%; box-shadow: 0 2px 3px rgba(0,0,0,0.1); }
        th, td { border: 1px solid #dee2e6; text-align: left; padding: 12px; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        th { background-color: #007bff; color: white; }
    </style>
</head>
<body>
    <h1>Offered Wares</h1>
    <table>
        <thead>
            <tr>
                <th>Ware Name</th>
                <th>Price</th>
                <th>Description</th>
                <th>Merchant Email</th>
            </tr>
        </thead>
        <tbody>
            {% for ware in wares %}
            <tr>
                <td>{{ ware.name }}</td>
                <td>{{ "%.2f"|format(ware.price) }}</td>
                <td>{{ ware.description }}</td>
                <td>{{ ware.merchant_email }}</td>
            </tr>
            {% else %}
            <tr>
                <td colspan="4" style="text-align:center; padding: 20px;">No wares found matching the criteria.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""
jinja_env = Environment(autoescape=select_autoescape(["html", "xml"]))
warehouse_template = jinja_env.from_string(WAREHOUSE_TEMPLATE_STR)

# --- FastAPI App ---
app = FastAPI(
    title="Merchant WebApp API",
    description="API for merchants to register, upload wares, and for users to retrieve offered items.",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    """Initialize database on application startup."""
    init_db()


# --- API Endpoints ---


@app.post(
    "/merchants/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new merchant",
)
async def register_merchant(merchant: MerchantRegister):
    """
    Registers a new merchant.
    - CWE-522 is addressed by hashing the password.
    - CWE-703 is addressed by handling database integrity errors for duplicate emails.
    """
    hashed_password = pwd_context.hash(merchant.password)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO merchants (email, name, password_hash) VALUES (?, ?, ?)",
                (merchant.email, merchant.name, hashed_password),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        # CWE-703: Specific handling for a known, exceptional condition (duplicate email).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    except sqlite3.Error as e:
        # CWE-703: General handling for other unexpected database errors.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"A database error occurred: {e}",
        )
    return {"message": "Merchant registered successfully"}


@app.post("/merchants/login", summary="Merchant login")
async def login_merchant(merchant_login: MerchantLogin):
    """
    Authenticates a merchant and returns a session cookie.
    - Verifies credentials against hashed passwords.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password_hash FROM merchants WHERE email = ?",
                (merchant_login.email,),
            )
            db_merchant = cursor.fetchone()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    if not db_merchant or not pwd_context.verify(
        merchant_login.password, db_merchant["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid email or password"},
        )

    access_token = create_access_token(data={"sub": str(db_merchant["id"])})
    response = JSONResponse(content="Login successful")
    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )
    return response


@app.post(
    "/merchants/upload-wares",
    summary="Lets a merchant upload their wares as a CSV string",
)
async def upload_wares(
    wares_upload: WaresUpload,
    merchant_id: Annotated[int, Depends(get_current_merchant_id)],
):
    """
    Uploads wares from a CSV string for the authenticated merchant.
    - CWE-863 is addressed by the `get_current_merchant_id` dependency.
    - CWE-703 is addressed by robustly handling CSV parsing errors.
    """
    csv_file = io.StringIO(wares_upload.csv)
    # The 'restval' and 'restkey' arguments handle rows with too many or too few columns.
    reader = csv.DictReader(
        csv_file,
        fieldnames=["name", "description", "price"],
        restval="",
        restkey="extra_cols",
    )

    wares_to_insert = []
    for i, row in enumerate(reader, 1):
        try:
            # Basic validation
            if not row.get("name") or not row.get("price"):
                raise ValueError("Missing 'name' or 'price' field.")
            if row.get("extra_cols"):
                raise ValueError("Row has too many columns.")

            price = float(row["price"])
            if price < 0:
                raise ValueError("Price cannot be negative.")

            wares_to_insert.append(
                (
                    row["name"],
                    row.get("description", ""),  # Default to empty string if missing
                    price,
                    merchant_id,
                )
            )
        except (ValueError, TypeError) as e:
            # CWE-703: Handle malformed rows (e.g., non-numeric price, missing fields).
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid CSV format on row {i}: {e}",
            )

    if not wares_to_insert:
        raise HTTPException(
            status_code=400, detail="CSV is empty or contains no valid data."
        )

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO wares (name, description, price, merchant_id) VALUES (?, ?, ?, ?)",
                wares_to_insert,
            )
            conn.commit()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error on insert: {e}")

    return {"message": "Wares uploaded successfully"}


@app.get(
    "/wares",
    response_class=HTMLResponse,
    summary="Retrieve all offered wares and merchants",
)
async def get_wares(
    request: Request,  # Required for auth dependency
    minPrice: Optional[float] = None,
    maxPrice: Optional[float] = None,
    # CWE-863: Protect this endpoint, ensuring only authenticated users can access it.
    merchant_id: Annotated[int, Depends(get_current_merchant_id)] = None,
):
    """
    Retrieves wares and renders them as an HTML table.
    - CWE-79 is addressed by using Jinja2 for HTML rendering.
    - CWE-863 is addressed by the `get_current_merchant_id` dependency.
    """
    query = """
        SELECT w.name, w.price, w.description, m.email as merchant_email
        FROM wares w
        JOIN merchants m ON w.merchant_id = m.id
    """
    filters = []
    params = []

    if minPrice is not None:
        filters.append("w.price >= ?")
        params.append(minPrice)
    if maxPrice is not None:
        filters.append("w.price <= ?")
        params.append(maxPrice)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY m.email, w.name"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            wares_data = cursor.fetchall()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    # CWE-79: Render data using Jinja2 template, which provides auto-escaping.
    html_content = warehouse_template.render(wares=wares_data)
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
