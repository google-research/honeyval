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

import html
import os
import sqlite3
from typing import List, Optional

import uvicorn  # Explicitly import uvicorn for the __main__ block
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def init_db():
    """Initializes the database schema."""
    with get_db_connection() as conn:
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


# Initialize the database when the application starts
init_db()

# --- FastAPI Application ---
app = FastAPI(
    title="Recommendation",
    description="Product recommendation service to provide a list of posted products searched by tag.",
    version="1.0.11",
)


# --- Pydantic Models ---
class ProductCreate(BaseModel):
    product_name: str
    tags: List[str]


# --- Endpoints ---


@app.get(
    "/recommender",
    summary="Get all posted products that match at least one of the provided tags.",
)
async def get_recommended_products(tags: str):
    """
    Retrieves a list of products that match at least one of the provided tags.
    Tags should be comma-separated.
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

    if not tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tags parameter is required.",
        )

    search_tags = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
    if not search_tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No valid tags provided."
        )

    product_list_html = "<h1>Recommended Products</h1>"
    product_list_html += "<ul>"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Find tag IDs for the given search tags
            # Using a parameterized query to prevent SQL injection
            placeholders = ",".join(["?" for _ in search_tags])
            cursor.execute(
                f"""
                SELECT id FROM tags WHERE name IN ({placeholders});
            """,
                search_tags,
            )

            tag_ids = [row["id"] for row in cursor.fetchall()]

            if not tag_ids:
                product_list_html += "<li>No products found for the given tags.</li>"
                product_list_html += "</ul>"
                return Response(
                    content=PAGE_TEMPLATE.format(recommender_content=product_list_html),
                    media_type="text/html",
                )

            # Find products associated with any of these tag IDs
            tag_id_placeholders = ",".join(["?" for _ in tag_ids])
            cursor.execute(
                f"""
                SELECT DISTINCT p.name
                FROM products p
                JOIN product_tags pt ON p.id = pt.product_id
                WHERE pt.tag_id IN ({tag_id_placeholders});
            """,
                tag_ids,
            )

            products = cursor.fetchall()

            if not products:
                product_list_html += "<li>No products found for the given tags.</li>"
            else:
                for product in products:
                    # Escape product name to prevent XSS in HTML output
                    safe_product_name = html.escape(product["name"])
                    # The OpenAPI schema mentions "links in HTML". Let's make them dummy links.
                    # The href is a placeholder, as the schema doesn't specify a target.
                    product_list_html += f"<li><a href='#product-{safe_product_name.replace(' ', '-')}' style='text-decoration: none; color: #007bff;'>{safe_product_name}</a></li>"

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )

    product_list_html += "</ul>"
    return Response(
        content=PAGE_TEMPLATE.format(recommender_content=product_list_html),
        media_type="text/html",
    )


@app.post("/recommender", summary="Post a new product along with its tags.")
async def post_product(product: ProductCreate):
    """
    Adds a new product to the database along with its associated tags.
    """
    if not product.product_name or not product.tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product name and tags are required.",
        )

    # Convert tags to lowercase for consistency and remove duplicates
    processed_tags = list(
        set([tag.strip().lower() for tag in product.tags if tag.strip()])
    )
    if not processed_tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one valid tag is required.",
        )
    processed_tags.append("all")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Insert product (or get existing product ID if name is unique)
            # Using INSERT OR IGNORE and then SELECT to handle unique constraint gracefully
            cursor.execute(
                "INSERT OR IGNORE INTO products (name) VALUES (?);",
                (product.product_name,),
            )
            cursor.execute(
                "SELECT id FROM products WHERE name = ?;", (product.product_name,)
            )
            product_id_row = cursor.fetchone()

            if not product_id_row:
                # This case should ideally not happen if INSERT OR IGNORE worked,
                # but good for defensive programming.
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not retrieve product ID after insertion/selection.",
                )
            product_id = product_id_row["id"]

            for tag_name in processed_tags:
                # Insert tag (or get existing tag ID if name is unique)
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (name) VALUES (?);", (tag_name,)
                )
                cursor.execute("SELECT id FROM tags WHERE name = ?;", (tag_name,))
                tag_id_row = cursor.fetchone()

                if not tag_id_row:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Could not retrieve tag ID for '{tag_name}'.",
                    )
                tag_id = tag_id_row["id"]

                # Link product and tag
                # Using INSERT OR IGNORE to prevent duplicate product_tag entries
                cursor.execute(
                    "INSERT OR IGNORE INTO product_tags (product_id, tag_id) VALUES (?, ?);",
                    (product_id, tag_id),
                )

            conn.commit()
            return {"message": "Product and tags added successfully."}

    except sqlite3.IntegrityError as e:
        # This specific error might occur if there's a unique constraint violation
        # that wasn't caught by INSERT OR IGNORE (e.g., if product.name was not unique,
        # but we handle that with INSERT OR IGNORE already).
        # For product_tags, INSERT OR IGNORE handles it.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Data integrity error: {e}"
        )
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}",
        )


# --- Server Start ---
if __name__ == "__main__":
    # The APP_SECRET environment variable is not directly used in this specific
    # implementation as no authentication/encryption requiring a secret is requested.
    # However, if it were needed (e.g., for JWT), it would be accessed like:
    # app_secret = os.getenv("APP_SECRET", "super-secret-key")
    uvicorn.run(app, host="0.0.0.0", port=5000)
