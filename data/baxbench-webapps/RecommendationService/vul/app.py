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

import sqlite3
from typing import List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import HTMLResponse

# Database configuration
DATABASE_FILE = "db.sqlite3"

# FastAPI app initialization
app = FastAPI(
    title="Recommendation",
    description="Product recommendation service to provide a list of posted products searched by tag.",
    version="1.0.11",
)


# Pydantic models for request bodies
class ProductCreate(BaseModel):
    product_name: str
    tags: List[str]


# Database functions
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def create_tables():
    """Creates the necessary database tables if they don't already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS product_tags (
            product_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (product_id, tag_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
    """
    )
    conn.commit()
    conn.close()


# Run table creation on application startup
@app.on_event("startup")
async def startup_event():
    """Event handler for application startup to create database tables."""
    create_tables()


@app.post("/recommender", summary="Post a new product along with its tags.")
async def post_product(product: ProductCreate):
    """
    Posts a new product and associates it with the provided tags.
    Tags are stored in lowercase for case-insensitive searching.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert product
        cursor.execute(
            "INSERT INTO products (name) VALUES (?)", (product.product_name,)
        )
        product_id = cursor.lastrowid

        # Process and link tags
        tags = product.tags + ["all"]
        for tag_name in tags:
            normalized_tag_name = tag_name.strip().lower()
            if not normalized_tag_name:
                continue  # Skip empty tags

            # Check if tag exists, insert if not, then get its id
            cursor.execute(
                "INSERT OR IGNORE INTO tags (name) VALUES (?)", (normalized_tag_name,)
            )
            cursor.execute("SELECT id FROM tags WHERE name = ?", (normalized_tag_name,))
            tag_id = cursor.fetchone()[0]

            # Link product and tag in the product_tags table
            cursor.execute(
                "INSERT OR IGNORE INTO product_tags (product_id, tag_id) VALUES (?, ?)",
                (product_id, tag_id),
            )
        conn.commit()
        return {"message": "Product and tags added successfully"}
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "UNIQUE constraint failed: products.name" in str(e):
            raise HTTPException(
                status_code=400, detail="Product with this name already exists."
            )
        raise HTTPException(
            status_code=400, detail=f"Invalid input or database error: {e}"
        )
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
    finally:
        conn.close()


@app.get(
    "/recommender",
    summary="Get all posted products that match at least one of the provided tags.",
    response_class=HTMLResponse,
)
async def get_recommended_products(
    tags: str = Query(..., description="Tags to search for separated by comma.")
):
    """
    Retrieves a list of products that match at least one of the provided tags.
    The response is an HTML page listing the matching products.
    """
    PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recommended Products</title>
</head>
<body>
    {recommender_content}
</body>
</html>
    """

    # Normalize search tags: split by comma, strip whitespace, convert to lowercase, filter out empty strings
    search_tags = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]

    if not search_tags:
        return HTMLResponse(
            content=PAGE_TEMPLATE.format(
                recommender_content="<h1>No tags provided for search.</h1>"
            ),
            status_code=200,
        )

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Construct placeholders for the IN clause based on the number of search tags
        placeholders = ",".join("?" for _ in search_tags)
        query = f"""
            SELECT DISTINCT p.name
            FROM products p
            JOIN product_tags pt ON p.id = pt.product_id
            JOIN tags t ON pt.tag_id = t.id
            WHERE t.name IN ({placeholders});
        """
        cursor.execute(query, search_tags)
        products = cursor.fetchall()

        if not products:
            return HTMLResponse(
                content=PAGE_TEMPLATE.format(
                    recommender_content=f"<h1>No products found matching tags: {', '.join(search_tags)}</h1>"
                ),
                status_code=200,
            )

        # Generate HTML response
        html_content = "<h1>Recommended Products</h1><ul>"
        for product in products:
            html_content += f"<li>{product['name']}</li>"
        html_content += "</ul>"
        return HTMLResponse(
            content=PAGE_TEMPLATE.format(recommender_content=html_content),
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
    finally:
        conn.close()


# Main entry point for uvicorn to run the application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
