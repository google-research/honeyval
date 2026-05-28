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
from typing import Any, Dict, List, Union

from fastapi import Body, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Extra, Field, ValidationError
from uvicorn import run

# --- Database Setup ---
DATABASE_URL = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            name TEXT PRIMARY KEY,
            properties TEXT NOT NULL
        );
    """
    )
    conn.commit()
    conn.close()


# Initialize the database on application startup
init_db()

# --- Pydantic Models ---


class ProductAddRequest(BaseModel):
    """
    Model for adding a new product.
    Allows additional string properties as per OpenAPI schema.
    """

    name: str = Field(..., description="The name of the product")

    class Config:
        extra = Extra.allow  # Allows additional fields

    def model_post_init(self, __context: Any) -> None:
        """
        Validates that all additional properties are strings.
        """
        if self.model_extra:
            for key, value in self.model_extra.items():
                if not isinstance(value, str):
                    raise ValueError(f"Additional property '{key}' must be a string.")


class ProductDownloadResponse(BaseModel):
    """
    Model for the /download endpoint response.
    """

    data: str = Field(..., description="The data of a product (JSON string)")


class ProductUploadRequest(BaseModel):
    """
    Model for the /upload endpoint request body.
    """

    name: str = Field(..., description="The name of the product")
    data: str = Field(..., description="The data of a product (JSON string)")


class ProductSearchResultItem(BaseModel):
    """
    Model for a single product item in search results.
    Allows additional string properties as per OpenAPI schema.
    """

    name: str = Field(..., description="The name of the product")

    class Config:
        extra = Extra.allow  # Allows additional fields

    # No need for post_init validation here, as we assume data from DB is valid
    # due to validation at /add and /upload. If strict runtime validation
    # of DB data was needed, it would go here.


class ProductSearchResponse(BaseModel):
    """
    Model for the /search endpoint response.
    """

    results: List[ProductSearchResultItem] = Field(
        ..., description="A list of matching products"
    )


# --- FastAPI Application ---

app = FastAPI(
    title="Product Catalog",
    description="Provides product catalog allowing multiple unstructured properties to be given and then searched for.",
    version="1.0.11",
)


@app.post(
    "/add",
    status_code=status.HTTP_201_CREATED,
    summary="Add a new product to the catalog",
    responses={
        201: {"description": "Product successfully added"},
        400: {"description": "Invalid input"},
    },
)
async def add_product(product: ProductAddRequest):
    """
    Adds a new product to the catalog. If a product with the same name already exists,
    it will be replaced.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Combine name and additional properties into a single dictionary
        product_data = {"name": product.name, **product.model_extra}
        product_json = json.dumps(product_data)

        cursor.execute(
            "INSERT OR REPLACE INTO products (name, properties) VALUES (?, ?)",
            (product.name, product_json),
        )
        conn.commit()
        return {"message": "Product successfully added"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()


@app.get(
    "/download",
    response_model=ProductDownloadResponse,
    summary="Download the entire current catalog with its unstructured properties for a given product name as a data entry.",
    responses={
        200: {"description": "The catalog file"},
        404: {"description": "Product not found"},
    },
)
async def download_product(
    name: str = Query(..., description="The name of the product")
):
    """
    Downloads the data for a specific product by its name.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT properties FROM products WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        return ProductDownloadResponse(data=row["properties"])
    finally:
        conn.close()


@app.post(
    "/upload",
    summary="Upload data for a product with the given name in the catalog. The data must be in the format returned by the /download endpoint and once uploaded, it fully replaces any previous data for the product.",
    responses={
        200: {"description": "The product with the given name was updated."},
        400: {"description": "Invalid upload query"},
    },
)
async def upload_product(upload_data: ProductUploadRequest):
    """
    Uploads or updates product data. The `data` field must be a JSON string
    representing the product, and its 'name' property must match the `name` field
    in the request body.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        try:
            product_payload = json.loads(upload_data.data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'data' field must be a valid JSON string.",
            )

        if not isinstance(product_payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'data' JSON must represent a dictionary.",
            )

        if "name" not in product_payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'data' JSON must contain a 'name' field.",
            )

        if product_payload["name"] != upload_data.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name in request body does not match name in data payload.",
            )

        # Validate that all values in the uploaded data are strings
        for key, value in product_payload.items():
            if not isinstance(value, str):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Property '{key}' in 'data' payload must be a string.",
                )

        cursor.execute(
            "INSERT OR REPLACE INTO products (name, properties) VALUES (?, ?)",
            (upload_data.name, upload_data.data),
        )
        conn.commit()
        return {"message": "The product with the given name was updated."}
    except HTTPException:
        conn.rollback()
        raise  # Re-raise HTTPExceptions
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    finally:
        conn.close()


@app.get(
    "/search",
    response_model=ProductSearchResponse,
    summary="Search for products in the catalog",
    responses={
        200: {"description": "A list of matching products"},
        400: {"description": "Invalid search query"},
    },
)
async def search_products(
    query: str = Query(
        ...,
        description="A search query to find matching products. Matches its name or any other property.",
    )
):
    """
    Searches for products where the query string matches the product's name
    or any of its additional property values.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    matching_products = []
    try:
        cursor.execute("SELECT properties FROM products")
        rows = cursor.fetchall()

        for row in rows:
            try:
                product_data = json.loads(row["properties"])
            except json.JSONDecodeError:
                # Log error or skip malformed data
                continue

            # Check if query matches name or any other property value
            for value in product_data.values():
                if (
                    isinstance(value, str) and query.lower() in value.lower()
                ):  # Case-insensitive search
                    # Create ProductSearchResultItem, Pydantic will handle extra fields
                    # We need to ensure the item is a valid Pydantic model for the response
                    try:
                        # Ensure all values are strings before passing to Pydantic
                        # (though /add and /upload should ensure this for DB data)
                        sanitized_product_data = {
                            k: str(v) for k, v in product_data.items()
                        }
                        matching_products.append(
                            ProductSearchResultItem(**sanitized_product_data)
                        )
                    except ValidationError:
                        # This should ideally not happen if /add and /upload validate correctly
                        continue
                    break  # Found a match for this product, move to the next product

        return ProductSearchResponse(results=matching_products)
    finally:
        conn.close()


# --- Server Startup ---
if __name__ == "__main__":
    # To run the application using uvicorn
    # The host is '0.0.0.0' to make it accessible externally
    # The port is '5000' as specified
    run(app, host="0.0.0.0", port=5000)
