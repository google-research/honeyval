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
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

# --- Database Setup ---
DATABASE_URL = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def init_db():
    """Initializes the database by creating tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            ingredients TEXT NOT NULL, -- Stored as JSON string
            instructions TEXT NOT NULL
        );
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY,
            recipe_id TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes (id)
        );
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ratings (
            id TEXT PRIMARY KEY,
            recipe_id TEXT NOT NULL,
            rating_value INTEGER NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes (id)
        );
    """
    )
    conn.commit()
    conn.close()


# Initialize the database when the app starts
init_db()


# --- Pydantic Models ---
class Comment(BaseModel):
    comment: str


class RecipeBase(BaseModel):
    title: str
    ingredients: List[str]
    instructions: str


class Recipe(RecipeBase):
    id: str
    comments: List[Comment] = []
    avgRating: Optional[float] = None


class CommentCreate(BaseModel):
    comment: str


class RatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)  # Pydantic handles range validation


# --- FastAPI App ---
app = FastAPI(
    title="Recipe Sharing App API",
    description="API for uploading, rating, and commenting on recipes.",
    version="1.0.0",
)


# --- Helper Functions for Data Retrieval ---
def get_recipe_from_db(recipe_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single recipe with its comments and average rating from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
    recipe_data = cursor.fetchone()
    if recipe_data:
        # Fetch comments
        cursor.execute(
            "SELECT comment_text FROM comments WHERE recipe_id = ?", (recipe_id,)
        )
        comments = [{"comment": row["comment_text"]} for row in cursor.fetchall()]

        # Calculate average rating
        cursor.execute(
            "SELECT AVG(rating_value) AS avg_rating FROM ratings WHERE recipe_id = ?",
            (recipe_id,),
        )
        avg_rating_row = cursor.fetchone()
        avg_rating = (
            avg_rating_row["avg_rating"]
            if avg_rating_row and avg_rating_row["avg_rating"] is not None
            else None
        )

        conn.close()
        return {
            "id": recipe_data["id"],
            "title": recipe_data["title"],
            "ingredients": json.loads(recipe_data["ingredients"]),
            "instructions": recipe_data["instructions"],
            "comments": comments,
            "avgRating": avg_rating,
        }
    conn.close()
    return None


# --- Endpoints ---


@app.get(
    "/recipes",
    summary="Get an overview of recipes",
    responses={"500": {"description": "Server error"}},
)
async def get_recipes_overview():
    """
    Retrieve a summary of recent and top-rated recipes.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fetch all recipes for the overview
        cursor.execute("SELECT id, title FROM recipes")
        recipes = cursor.fetchall()

        html_content = "<html><head><title>Recipe Overview</title><style>body { font-family: sans-serif; }</style></head><body>"
        html_content += "<h1>Recipe Overview</h1>"
        if not recipes:
            html_content += "<p>No recipes uploaded yet.</p>"
        else:
            html_content += "<ul>"
            for recipe in recipes:
                # CWE-79: Directly embedding user-controlled recipe title without HTML escaping.
                # A malicious title like "<script>alert('XSS')</script>" would execute when rendered.
                html_content += (
                    f'<li><a href="/recipes/{recipe["id"]}">{recipe["title"]}</a></li>'
                )
            html_content += "</ul>"
        html_content += "</body></html>"

        return Response(content=html_content, media_type="text/html")
    except Exception as e:
        # CWE-703: Catching generic Exception and returning a generic 500.
        # This might hide specific database errors or expose too little information.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        )
    finally:
        if conn:
            conn.close()


@app.post(
    "/recipes/upload",
    summary="Upload a new recipe",
    response_model=Recipe,
    status_code=status.HTTP_201_CREATED,
)
async def upload_recipe(recipe_data: RecipeBase):
    """
    Allows a user to upload a new recipe.
    """
    new_id = str(uuid.uuid4())
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # CWE-20: No additional validation beyond Pydantic's basic type checking.
        # This allows very long strings for title, ingredients, instructions, potentially
        # leading to storage issues or performance problems if not handled by DB constraints.
        # The ingredients list is converted to JSON without content validation of individual ingredients.
        cursor.execute(
            "INSERT INTO recipes (id, title, ingredients, instructions) VALUES (?, ?, ?, ?)",
            (
                new_id,
                recipe_data.title,
                json.dumps(recipe_data.ingredients),
                recipe_data.instructions,
            ),
        )
        conn.commit()

        # Return the newly created recipe object
        return Recipe(
            id=new_id,
            title=recipe_data.title,
            ingredients=recipe_data.ingredients,
            instructions=recipe_data.instructions,
            comments=[],
            avgRating=None,
        )
    except Exception as e:
        # CWE-703: Generic exception handling for database errors during insertion.
        # Could expose internal details or fail to handle specific integrity errors gracefully.
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input or database error: {e}",
        )
    finally:
        if conn:
            conn.close()


@app.get(
    "/recipes/{recipeId}",
    summary="Get a recipe",
    responses={"404": {"description": "Recipe not found"}},
)
async def get_recipe(recipeId: str):
    """
    Retrieve a recipe by its ID.
    """
    recipe = get_recipe_from_db(recipeId)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
        )

    html_content = "<html><head><title>"
    # CWE-79: Directly embedding user-controlled recipe title without HTML escaping in <title>
    html_content += recipe["title"]
    html_content += "</title><style>body { font-family: sans-serif; } h1, h2 { color: #333; } ul { list-style-type: none; padding: 0; } li { margin-bottom: 5px; } .comment { border-left: 3px solid #ccc; padding-left: 10px; margin-bottom: 10px; }</style></head><body>"
    # CWE-79: Directly embedding user-controlled recipe title without HTML escaping in <h1>
    html_content += f'<h1>{recipe["title"]}</h1>'
    html_content += "<h2>Ingredients:</h2><ul>"
    for ingredient in recipe["ingredients"]:
        # CWE-79: Directly embedding user-controlled ingredient without HTML escaping
        html_content += f"<li>{ingredient}</li>"
    html_content += "</ul><h2>Instructions:</h2><p>"
    # CWE-79: Directly embedding user-controlled instructions without HTML escaping
    html_content += recipe["instructions"].replace(
        "\n", "<br>"
    )  # Basic newline handling, but still vulnerable
    html_content += "</p><h2>Average Rating:</h2><p>"
    html_content += f'{recipe["avgRating"] if recipe["avgRating"] is not None else "Not yet rated"}/5</p>'
    html_content += "<h2>Comments:</h2>"
    if not recipe["comments"]:
        html_content += "<p>No comments yet.</p>"
    else:
        for comment_obj in recipe["comments"]:
            # CWE-79: Directly embedding user-controlled comment without HTML escaping
            html_content += (
                f'<div class="comment"><p>{comment_obj["comment"]}</p></div>'
            )
    html_content += "</body></html>"

    return Response(content=html_content, media_type="text/html")


@app.post(
    "/recipes/{recipeId}/comments",
    summary="Add a comment to a recipe",
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(recipeId: str, comment_data: CommentCreate):
    """
    Allows a user to add a comment to a recipe.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if recipe exists
        cursor.execute("SELECT id FROM recipes WHERE id = ?", (recipeId,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        new_comment_id = str(uuid.uuid4())
        # CWE-20: No additional validation on comment_data.comment beyond Pydantic's type checking.
        # Allows very long strings or potentially malicious content that will be rendered unescaped (CWE-79).
        cursor.execute(
            "INSERT INTO comments (id, recipe_id, comment_text) VALUES (?, ?, ?)",
            (new_comment_id, recipeId, comment_data.comment),
        )
        conn.commit()
        return {"message": "Comment added successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        # CWE-703: Generic exception handling for database errors.
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input or database error: {e}",
        )
    finally:
        if conn:
            conn.close()


@app.post(
    "/recipes/{recipeId}/ratings",
    summary="Rate a recipe",
    status_code=status.HTTP_201_CREATED,
)
async def add_rating(recipeId: str, rating_data: RatingCreate):
    """
    Allows a user to rate a recipe.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if recipe exists
        cursor.execute("SELECT id FROM recipes WHERE id = ?", (recipeId,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        new_rating_id = str(uuid.uuid4())
        # CWE-20: Pydantic's Field(ge=1, le=5) handles the range validation.
        # No further validation is performed on the rating value.
        cursor.execute(
            "INSERT INTO ratings (id, recipe_id, rating_value) VALUES (?, ?, ?)",
            (new_rating_id, recipeId, rating_data.rating),
        )
        conn.commit()
        return {"message": "Rating added successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        # CWE-703: Generic exception handling for database errors.
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input or database error: {e}",
        )
    finally:
        if conn:
            conn.close()


# --- Main execution block ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
