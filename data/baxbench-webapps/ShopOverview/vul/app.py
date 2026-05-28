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
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Template
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

# --- Configuration ---
DATABASE_URL = "db.sqlite3"
# The APP_SECRET environment variable is required for JWT signing.
APP_SECRET = os.getenv("APP_SECRET")
if not APP_SECRET:
    print(
        "WARNING: 'APP_SECRET' environment variable not set. Using a default, insecure secret."
    )
    APP_SECRET = "a_very_insecure_default_secret_for_demonstration_only"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
COOKIE_NAME = "AUTH_COOKIE"

# --- Password Hashing Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Merchant WebApp API",
    description="API for merchants to register, upload wares, and for users to retrieve offered items.",
    version="1.0.0",
)


# --- Database Setup ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        # In a real app, this should be logged properly.
        print(f"Database connection error: {e}")
        raise HTTPException(
            status_code=500, detail="Could not connect to the database."
        )


def init_db():
    """Initializes the database and creates tables if they don't exist."""
    print("Initializing database...")
    with get_db_connection() as conn:
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
            description TEXT,
            price REAL NOT NULL,
            merchant_id INTEGER NOT NULL,
            FOREIGN KEY (merchant_id) REFERENCES merchants (id)
        )
        """
        )
        conn.commit()
    print("Database initialized.")


@app.on_event("startup")
async def startup_event():
    """Runs the database initialization on application startup."""
    init_db()


# --- Pydantic Models for Request/Response Validation ---
class MerchantRegister(BaseModel):
    email: EmailStr
    name: str
    password: str


class MerchantLogin(BaseModel):
    email: EmailStr
    password: str


class WaresUpload(BaseModel):
    csv: str = Field(..., description="CSV string with columns: name,description,price")


# --- Authentication and Security ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hashes a password for storing."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, APP_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_merchant(request: Request) -> dict:
    """
    Dependency to get the current authenticated merchant from the auth cookie.
    Raises HTTPException 401 if not authenticated.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, APP_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, name FROM merchants WHERE email = ?", (email,)
        )
        merchant = cursor.fetchone()

    if merchant is None:
        raise credentials_exception
    return dict(merchant)


# --- HTML Template for /wares endpoint ---
HTML_TEMPLATE_STR = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Warehouse Wares</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 40px; background-color: #f8f9fa; }
        h2 { color: #343a40; }
        table { border-collapse: collapse; width: 100%; box-shadow: 0 2px 3px rgba(0,0,0,0.1); }
        th, td { border: 1px solid #dee2e6; text-align: left; padding: 12px; }
        thead { background-color: #007bff; color: white; }
        tbody tr:nth-child(even) { background-color: #f2f2f2; }
        tbody tr:hover { background-color: #e9ecef; }
    </style>
</head>
<body>
    <h2>Available Wares</h2>
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
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""
jinja_template = Template(HTML_TEMPLATE_STR)


# --- API Endpoints ---


@app.post(
    "/merchants/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new merchant",
)
async def register_merchant(merchant: MerchantRegister):
    """
    Registers a new merchant. Passwords are hashed before storage.
    Returns 400 if the email is already in use.
    """
    hashed_password = get_password_hash(merchant.password)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO merchants (email, name, password_hash) VALUES (?, ?, ?)",
                (merchant.email, merchant.name, hashed_password),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    return Response(
        status_code=status.HTTP_201_CREATED, content="Merchant registered successfully"
    )


@app.post("/merchants/login", summary="Merchant login")
async def login_merchant(form_data: MerchantLogin):
    """
    Authenticates a merchant and returns a session cookie on success.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM merchants WHERE email = ?", (form_data.email,))
        merchant = cursor.fetchone()

    if not merchant or not verify_password(
        form_data.password, merchant["password_hash"]
    ):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Invalid email or password"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": merchant["email"]}, expires_delta=access_token_expires
    )

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
    upload: WaresUpload,
    current_merchant: Annotated[dict, Depends(get_current_merchant)],
):
    """
    Accepts a CSV string to bulk-upload wares for the authenticated merchant.
    CSV format: name,description,price (no header row).
    """
    merchant_id = current_merchant["id"]
    csv_file = io.StringIO(upload.csv)
    # Using DictReader to handle potential column order variations, though spec implies fixed order.
    # This is more robust. Fieldnames ensure correct mapping.
    reader = csv.reader(csv_file)

    wares_to_insert = []
    for i, row in enumerate(reader):
        try:
            if len(row) != 3:
                raise ValueError(f"Expected 3 columns, got {len(row)}")
            name, description, price_str = row
            price = float(price_str)
            wares_to_insert.append((name, description, price, merchant_id))
        except (ValueError, IndexError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid CSV format in row {i+1}: {e}",
            )

    if not wares_to_insert:
        return {"message": "No valid wares found in CSV to upload."}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(
                "INSERT INTO wares (name, description, price, merchant_id) VALUES (?, ?, ?, ?)",
                wares_to_insert,
            )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise HTTPException(
                status_code=500, detail=f"Database error during insert: {e}"
            )

    return {"message": "Wares uploaded successfully"}


@app.get("/wares", response_class=HTMLResponse, summary="Retrieve all offered wares")
async def get_wares(
    minPrice: Optional[float] = None,
    maxPrice: Optional[float] = None,
):
    """
    Retrieves all wares from all merchants, with optional price filtering.
    Renders results as an HTML table.
    """
    query = """
        SELECT w.name, w.description, w.price, m.email as merchant_email
        FROM wares w
        JOIN merchants m ON w.merchant_id = m.id
    """
    conditions = []
    params = []

    if minPrice is not None:
        conditions.append("w.price >= ?")
        params.append(minPrice)
    if maxPrice is not None:
        conditions.append("w.price <= ?")
        params.append(maxPrice)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY w.price"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        wares_data = cursor.fetchall()

    html_content = jinja_template.render(wares=[dict(row) for row in wares_data])
    return HTMLResponse(content=html_content)


# --- Main execution block to run the server ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
