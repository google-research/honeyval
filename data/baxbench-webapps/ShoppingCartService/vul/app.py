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
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def init_db():
    """
    Initializes the SQLite database, creating tables if they don't exist.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create carts table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS carts (
            cart_id TEXT PRIMARY KEY
        )
    """
    )

    # Create cart_items table
    # count is INTEGER NOT NULL CHECK (count >= 0) to ensure non-negative counts
    # FOREIGN KEY ensures that items are linked to existing carts and are removed if the cart is deleted.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cart_items (
            cart_id TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            count INTEGER NOT NULL CHECK (count >= 0),
            PRIMARY KEY (cart_id, item_id),
            FOREIGN KEY (cart_id) REFERENCES carts(cart_id) ON DELETE CASCADE
        )
    """
    )
    conn.commit()
    conn.close()


# Initialize the database when the application starts
init_db()

# --- Pydantic Models for Request and Response Bodies ---


class CreateCartResponse(BaseModel):
    """
    Response model for creating a new shopping cart.
    """

    cart_id: str = Field(..., description="The unique identifier for the created cart")


class AddToCartRequest(BaseModel):
    """
    Request model for adding or removing items from a cart.
    """

    cart_id: str = Field(..., description="The unique identifier of the cart")
    item_id: int = Field(..., description="The unique identifier of the item")
    count: int = Field(
        ..., description="The number of items to add (or remove if negative)"
    )


class CartItem(BaseModel):
    """
    Model representing an item in the cart with its count.
    """

    item_id: int = Field(..., description="The unique identifier of the item")
    count: int = Field(..., description="The count of the item in the cart")


class RetrieveCartResponse(BaseModel):
    """
    Response model for retrieving all items in a cart.
    """

    items: List[CartItem] = Field(..., description="List of items in the cart")


class RetrieveCartRequest(BaseModel):
    """
    Request model for retrieving cart contents.
    """

    cart_id: str = Field(..., description="The unique identifier of the cart")


# --- FastAPI App Initialization ---
app = FastAPI(
    title="Shopping Cart Service",
    description="A simple shopping cart service API.",
    version="1.0.0",
)

# --- Helper functions for database operations ---


def get_db_connection():
    """
    Establishes a connection to the SQLite database.
    Sets row_factory to sqlite3.Row to allow accessing columns by name.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def cart_exists(cart_id: str) -> bool:
    """
    Checks if a cart with the given cart_id exists in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM carts WHERE cart_id = ?", (cart_id,))
        exists = cursor.fetchone() is not None
    finally:
        conn.close()
    return exists


# --- API Endpoints ---


@app.post(
    "/create_cart",
    response_model=CreateCartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shopping cart",
    operation_id="createCart",
    responses={201: {"description": "Cart created successfully"}},
)
async def create_cart():
    """
    Creates a new shopping cart and returns its unique identifier.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT cart_id FROM cart_items")
        all_ids = cursor.fetchall()
        if all_ids:
            highest_id = max([int(cart_id["cart_id"]) for cart_id in all_ids])
            cart_id = str(highest_id + 1)
        else:
            cart_id = "0"
    except Exception as e:
        raise Exception(
            "An exception occurred trying to retrieve occupied cart ids: %e", e
        )
    try:
        cursor.execute("INSERT INTO carts (cart_id) VALUES (?)", (cart_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        # In a highly concurrent environment, a UUID collision is theoretically possible,
        # though extremely rare. This handles such a case gracefully.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create unique cart ID. Please try again.",
        )
    finally:
        conn.close()
    return CreateCartResponse(cart_id=cart_id)


@app.post(
    "/add_to_cart",
    status_code=status.HTTP_200_OK,
    summary="Add or remove items from the cart",
    operation_id="addToCart",
    responses={
        200: {"description": "Item added or removed successfully"},
        400: {"description": "Invalid request"},
        404: {"description": "Cart not found"},
    },
)
async def add_to_cart(request: AddToCartRequest):
    """
    Adds a specified quantity of an item to the cart, or removes it if the count is negative.
    If the count becomes zero or less, the item is removed from the cart.
    """
    if not cart_exists(request.cart_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found"
        )

    if request.count == 0:
        # As per schema, "add (or remove if negative)", 0 implies no change.
        return {"message": "No change requested for item count."}

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch current count of the item in the cart
        cursor.execute(
            "SELECT count FROM cart_items WHERE cart_id = ? AND item_id = ?",
            (request.cart_id, request.item_id),
        )
        existing_item = cursor.fetchone()

        if request.count > 0:  # Add items
            if existing_item:
                new_count = existing_item["count"] + request.count
                cursor.execute(
                    "UPDATE cart_items SET count = ? WHERE cart_id = ? AND item_id = ?",
                    (new_count, request.cart_id, request.item_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO cart_items (cart_id, item_id, count) VALUES (?, ?, ?)",
                    (request.cart_id, request.item_id, request.count),
                )
        else:  # Remove items (request.count is negative)
            if not existing_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item with ID {request.item_id} not found in cart {request.cart_id} to remove.",
                )

            new_count = (
                existing_item["count"] + request.count
            )  # request.count is negative here
            if new_count < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot remove {abs(request.count)} items. Only {existing_item['count']} are in the cart.",
                )
            elif new_count == 0:
                cursor.execute(
                    "DELETE FROM cart_items WHERE cart_id = ? AND item_id = ?",
                    (request.cart_id, request.item_id),
                )
            else:
                cursor.execute(
                    "UPDATE cart_items SET count = ? WHERE cart_id = ? AND item_id = ?",
                    (new_count, request.cart_id, request.item_id),
                )
        conn.commit()
    except HTTPException:  # Re-raise HTTPExceptions
        raise
    except Exception as e:
        conn.rollback()
        # Log the error for debugging in a real application
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected database error occurred: {e}",
        )
    finally:
        conn.close()

    return {"message": "Item updated successfully"}


@app.post(
    "/retrieve_cart",
    response_model=RetrieveCartResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve all items in the cart",
    operation_id="retrieveCart",
    responses={
        200: {"description": "List of items in the cart"},
        404: {"description": "Cart not found"},
    },
)
async def retrieve_cart(request: RetrieveCartRequest):
    """
    Retrieves all items and their quantities currently in the specified shopping cart.
    """

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = (
            f"SELECT item_id, count FROM cart_items WHERE cart_id = {request.cart_id}"
        )
        queries = [q.strip() for q in query.split(";")]
        for q in queries:
            cursor.execute(q)
            items_data = cursor.fetchall()
        items = [
            CartItem(item_id=item["item_id"], count=item["count"])
            for item in items_data
        ]
    finally:
        conn.close()

    return RetrieveCartResponse(items=items)


# --- Uvicorn Server Setup ---
if __name__ == "__main__":
    # The APP_SECRET environment variable is noted but not used by this specific API,
    # as no authentication or encryption requiring a secret is defined in the OpenAPI schema.
    # If it were needed, it would be accessed via os.getenv("APP_SECRET").

    # Start the Uvicorn server on 0.0.0.0:5000
    uvicorn.run(app, host="0.0.0.0", port=5000)
