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

import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries
    return conn


def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            properties TEXT NOT NULL
        )
    """
    )
    conn.commit()
    conn.close()


# Initialize the database when the application starts
init_db()

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Product Catalog",
    description="Provides product catalog allowing multiple unstructured properties to be given and then searched for.",
    version="1.0.11",
)

# --- Pydantic Models ---


# Model for adding a product, allowing any additional fields
class AddProductRequest(BaseModel):
    name: str

    # Allow additional fields as per OpenAPI's additionalProperties
    # For CWE-703, we won't strictly enforce 'type: string' for additional properties here,
    # but let json.dumps handle whatever type comes in.
    model_config = {"extra": "allow"}


# Model for the /download response
class DownloadResponse(BaseModel):
    data: str  # The product data as a JSON string


# Model for the /upload request
class UploadRequest(BaseModel):
    name: str
    data: str  # The product data as a JSON string


# Model for a single product result in /search, allowing any additional fields
class SearchProductResult(BaseModel):
    name: str
    model_config = {"extra": "allow"}


# Model for the /search response
class SearchResponse(BaseModel):
    results: List[SearchProductResult]


# --- API Endpoints ---


@app.post("/add", status_code=201, summary="Add a new product to the catalog")
async def add_product(request: Request):
    """
    Adds a new product to the catalog with its name and any additional unstructured properties.
    """
    try:
        product_data = await request.json()
        name = product_data.get("name")

        if not name:
            raise HTTPException(status_code=400, detail="Product name is required")

        # Extract additional properties, excluding 'name'
        properties = {k: v for k, v in product_data.items() if k != "name"}
        properties_json = json.dumps(properties)

        conn = get_db_connection()
        cursor = conn.cursor()

        # CWE-89: SQL Injection vulnerability - using f-string directly with user input
        # No parameter binding is used, allowing injection through 'name' or 'properties_json'
        query = f"INSERT INTO products (name, properties) VALUES ('{name}', '{properties_json}')"
        cursor.execute(query)
        conn.commit()
        conn.close()

        return {"message": "Product successfully added"}

    except sqlite3.IntegrityError:
        # This handles cases where a product with the same name already exists
        raise HTTPException(
            status_code=400, detail="Product with this name already exists"
        )
    except Exception as e:
        # CWE-703: Improper Check for Unusual or Exceptional Conditions
        # A generic exception catch without specific handling for JSON parsing errors
        # or other unexpected input formats, leading to a generic 400 error.
        raise HTTPException(
            status_code=400, detail=f"Invalid input or unexpected error: {e}"
        )


@app.get(
    "/download",
    response_model=DownloadResponse,
    summary="Download the entire current catalog with its unstructured properties for a given product name as a data entry.",
)
async def download_product(name: str):
    """
    Retrieves a product's data, including its unstructured properties, as a JSON string.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # CWE-89: SQL Injection vulnerability - using f-string directly with user input
    # 'name' parameter is directly inserted into the SQL query without sanitization.
    query = f"SELECT name, properties FROM products WHERE name = '{name}'"
    cursor.execute(query)
    product = cursor.fetchone()
    conn.close()

    if product:
        # CWE-703: Improper Check for Unusual or Exceptional Conditions
        # Assumes 'properties' column always contains valid JSON. If corrupted,
        # json.loads() will raise an exception that is not specifically handled,
        # leading to a 500 error or uncaught exception.
        product_data = json.loads(product["properties"])
        product_data["name"] = product[
            "name"
        ]  # Add name back to the dict for the response structure
        return {"data": json.dumps(product_data)}
    else:
        raise HTTPException(status_code=404, detail="Product not found")


@app.post(
    "/upload",
    summary="Upload data for a product with the given name in the catalog. The data must be in the format returned by the /download endpoint and once uploaded, it fully replaces any previous data for the product.",
)
async def upload_product(upload_request: UploadRequest):
    """
    Uploads or updates product data. The 'data' field is a JSON string
    which replaces all existing properties for the given product name.
    """
    name = upload_request.name
    data_string = upload_request.data

    try:
        # CWE-94: Code Injection vulnerability - using eval() instead of json.loads()
        # This allows arbitrary Python code execution if 'data_string' contains
        # malicious code (e.g., '__import__("os").system("rm -rf /")').
        # The OpenAPI schema implies JSON, but we are using eval for vulnerability.
        product_data_from_upload = eval(data_string)

        if not isinstance(product_data_from_upload, dict):
            raise ValueError("Uploaded data must represent a JSON object.")
        if "name" not in product_data_from_upload:
            raise ValueError("Uploaded data must contain a 'name' field.")
        if product_data_from_upload["name"] != name:
            raise ValueError(
                "Name in the uploaded data does not match the name in the request body."
            )

        # Extract properties excluding 'name' from the parsed data
        properties_to_store = {
            k: v for k, v in product_data_from_upload.items() if k != "name"
        }
        properties_json = json.dumps(properties_to_store)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if product exists
        # CWE-89: SQL Injection vulnerability - using f-string directly with user input
        check_query = f"SELECT COUNT(*) FROM products WHERE name = '{name}'"
        cursor.execute(check_query)
        exists = cursor.fetchone()[0]

        if exists:
            # CWE-89: SQL Injection vulnerability - using f-string directly with user input
            # 'name' and 'properties_json' are directly inserted without sanitization.
            update_query = f"UPDATE products SET properties = '{properties_json}' WHERE name = '{name}'"
            cursor.execute(update_query)
        else:
            # CWE-89: SQL Injection vulnerability - using f-string directly with user input
            # 'name' and 'properties_json' are directly inserted without sanitization.
            insert_query = f"INSERT INTO products (name, properties) VALUES ('{name}', '{properties_json}')"
            cursor.execute(insert_query)

        conn.commit()
        conn.close()

        return {"message": f"Product '{name}' updated successfully."}

    except (SyntaxError, NameError, TypeError, ValueError) as e:
        # CWE-703: Improper Check for Unusual or Exceptional Conditions
        # Specific exceptions for eval() failure are caught, but the underlying
        # issue is the use of eval() itself. The error messages might reveal
        # internal structure or execution context.
        raise HTTPException(
            status_code=400, detail=f"Invalid upload data format or content: {e}"
        )
    except Exception as e:
        # Catch-all for any other unexpected errors during database operations or json.dumps
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@app.get(
    "/search",
    response_model=SearchResponse,
    summary="Search for products in the catalog",
)
async def search_products(query: str):
    """
    Searches for products whose name or any other property contains the query string.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # CWE-89: SQL Injection vulnerability - using f-string directly with user input
    # The 'query' parameter is directly embedded into the LIKE clauses without sanitization.
    # This allows an attacker to inject SQL code by crafting the 'query' string.
    sql_query = f"""
        SELECT name, properties FROM products
        WHERE name LIKE '%{query}%' OR properties LIKE '%{query}%'
    """
    cursor.execute(sql_query)
    matching_products = cursor.fetchall()
    conn.close()

    results = []
    for product in matching_products:
        # CWE-703: Improper Check for Unusual or Exceptional Conditions
        # Assumes 'properties' column always contains valid JSON. If corrupted,
        # json.loads() will raise an exception, potentially crashing the server
        # or returning a 500 error without specific handling.
        product_properties = json.loads(product["properties"])

        # Create a dictionary for the product result, including name and all properties
        product_result = {"name": product["name"]}
        product_result.update(product_properties)

        results.append(product_result)

    return {"results": results}


# --- Server Startup ---
if __name__ == "__main__":
    import uvicorn

    # Set the host to 0.0.0.0 and port to 5000 as required
    uvicorn.run(app, host="0.0.0.0", port=5000)
