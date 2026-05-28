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
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
from jinja2 import Environment, select_autoescape
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn


def create_tables():
    """Creates necessary database tables if they don't already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Recipes table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT NOT NULL
        )
    """
    )
    # Comments table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    """
    )
    # Ratings table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id TEXT NOT NULL,
            rating_value INTEGER NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    """
    )
    conn.commit()
    conn.close()


# Initialize tables on application startup
create_tables()

# --- Pydantic Models ---


# Model for the request body when uploading a new recipe
class RecipeUpload(BaseModel):
    title: str
    ingredients: List[str]
    instructions: str


# Model for the request body when adding a comment
class CommentCreate(BaseModel):
    comment: str


# Model for the request body when adding a rating
class RatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating value between 1 and 5.")


# Model for a comment stored in DB and included in Recipe response
class CommentDB(BaseModel):
    comment: str


# Full Recipe model for responses, including ID, comments, and average rating
class Recipe(BaseModel):
    id: str
    title: str
    ingredients: List[str]
    instructions: str
    comments: List[CommentDB] = []
    avgRating: Optional[float] = None


# Model for recipe items in the overview list (used internally for HTML rendering)
class RecipeOverviewItem(BaseModel):
    id: str
    title: str


# --- FastAPI App ---
app = FastAPI(
    title="Recipe Sharing App API",
    description="API for uploading, rating, and commenting on recipes.",
    version="1.0.0",
)

# --- Jinja2 Setup for HTML rendering ---
# Using a basic Jinja2 environment to render HTML templates from strings.
env = Environment(
    loader=None,  # Templates are loaded directly from strings
    autoescape=select_autoescape(["html", "xml"]),
)

# Define HTML templates as strings
RECIPE_OVERVIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Recipe Overview</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"; margin: 20px; background-color: #f8f9fa; color: #343a40; }
        h1 { color: #007bff; margin-bottom: 20px; }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; background-color: #ffffff; border: 1px solid #e0e0e0; padding: 10px 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,.05); }
        a { text-decoration: none; color: #007bff; font-weight: 500; }
        a:hover { text-decoration: underline; color: #0056b3; }
        p { color: #6c757d; }
        .upload-link { display: inline-block; margin-top: 20px; padding: 10px 15px; background-color: #28a745; color: white; border-radius: 5px; text-decoration: none; }
        .upload-link:hover { background-color: #218838; }
    </style>
</head>
<body>
    <h1>Recipe Overview</h1>
    {% if recipes %}
    <ul>
        {% for recipe in recipes %}
        <li><a href="/recipes/{{ recipe.id }}">{{ recipe.title }}</a></li>
        {% endfor %}
    </ul>
    {% else %}
    <p>No recipes available yet.</p>
    <a class="upload-link" href="/docs#/Recipe%20Management/upload_new_recipe_recipes_upload_post">Upload Your First Recipe!</a>
    {% endif %}
</body>
</html>
"""

SINGLE_RECIPE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ recipe.title }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"; margin: 20px; line-height: 1.6; background-color: #f8f9fa; color: #343a40; }
        .container { max-width: 800px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.08); }
        h1 { color: #007bff; margin-bottom: 15px; }
        h2 { color: #6c757d; border-bottom: 1px solid #e9ecef; padding-bottom: 8px; margin-top: 30px; margin-bottom: 15px; font-size: 1.5em; }
        ul, ol { margin-left: 20px; padding-left: 0; }
        li { margin-bottom: 8px; }
        p { margin-bottom: 10px; }
        .rating { font-size: 1.1em; font-weight: bold; color: #fd7e14; margin-bottom: 15px; }
        .comment { background-color: #e9ecef; border: 1px solid #dee2e6; padding: 12px; margin-bottom: 10px; border-radius: 5px; }
        .comment p { margin: 0; color: #495057; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; color: #0056b3; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #6c757d; }
        .back-link:hover { color: #495057; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/recipes" class="back-link">&lt; Back to all recipes</a>
        <h1>{{ recipe.title }}</h1>
        {% if recipe.avgRating is not none %}
        <p class="rating">Average Rating: {{ "%.1f" | format(recipe.avgRating) }} / 5</p>
        {% else %}
        <p class="rating">No ratings yet.</p>
        {% endif %}

        <h2>Ingredients</h2>
        <ul>
            {% for ingredient in recipe.ingredients %}
            <li>{{ ingredient }}</li>
            {% endfor %}
        </ul>

        <h2>Instructions</h2>
        <p>{{ recipe.instructions | replace("\\n", "<br>") }}</p>

        <h2>Comments</h2>
        {% if recipe.comments %}
            {% for comment in recipe.comments %}
            <div class="comment">
                <p>{{ comment.comment }}</p>
            </div>
            {% endfor %}
        {% else %}
        <p>No comments yet. Be the first to comment!</p>
        {% endif %}
    </div>
</body>
</html>
"""

# --- Helper Functions for DB Operations ---


def get_recipe_from_db(recipe_id: str) -> Optional[Recipe]:
    """
    Retrieves a single recipe from the database by its ID,
    including its comments and calculated average rating.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, title, ingredients, instructions FROM recipes WHERE id = ?",
            (recipe_id,),
        )
        recipe_row = cursor.fetchone()
        if not recipe_row:
            return None

        recipe_data = dict(recipe_row)
        recipe_data["ingredients"] = json.loads(recipe_data["ingredients"])

        # Get comments for the recipe
        cursor.execute(
            "SELECT comment_text FROM comments WHERE recipe_id = ?", (recipe_id,)
        )
        comment_rows = cursor.fetchall()
        recipe_data["comments"] = [
            CommentDB(comment=row["comment_text"]) for row in comment_rows
        ]

        # Get average rating for the recipe
        cursor.execute(
            "SELECT AVG(rating_value) AS avg_rating FROM ratings WHERE recipe_id = ?",
            (recipe_id,),
        )
        rating_row = cursor.fetchone()
        avg_rating = (
            rating_row["avg_rating"]
            if rating_row and rating_row["avg_rating"] is not None
            else None
        )
        recipe_data["avgRating"] = avg_rating

        return Recipe(**recipe_data)
    finally:
        conn.close()


def get_all_recipes_for_overview() -> List[RecipeOverviewItem]:
    """
    Retrieves a list of all recipe IDs and titles for the overview page.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title FROM recipes ORDER BY title ASC")
        recipe_rows = cursor.fetchall()
        return [
            RecipeOverviewItem(id=row["id"], title=row["title"]) for row in recipe_rows
        ]
    finally:
        conn.close()


# --- API Endpoints ---


@app.get("/recipes", summary="Get an overview of recipes", response_class=HTMLResponse)
async def get_recipe_overview():
    """
    Retrieve a summary of all available recipes.
    Returns an HTML page with recipe titles and links to their full details.
    """
    try:
        recipes = get_all_recipes_for_overview()
        # Render the HTML template using Jinja2
        template = env.from_string(RECIPE_OVERVIEW_TEMPLATE)
        html_content = template.render(recipes=recipes)
        return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
    except Exception as e:
        # Catch any unexpected errors and return a 500 status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {e}",
        )


@app.post(
    "/recipes/upload",
    summary="Upload a new recipe",
    response_model=Recipe,
    status_code=status.HTTP_201_CREATED,
)
async def upload_new_recipe(recipe_data: RecipeUpload):
    """
    Allows a user to upload a new recipe.
    The recipe details (title, ingredients, instructions) are provided in the request body.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        recipe_id = str(uuid.uuid4())  # Generate a unique ID for the new recipe
        ingredients_json = json.dumps(
            recipe_data.ingredients
        )  # Store list of ingredients as JSON string

        cursor.execute(
            "INSERT INTO recipes (id, title, ingredients, instructions) VALUES (?, ?, ?, ?)",
            (recipe_id, recipe_data.title, ingredients_json, recipe_data.instructions),
        )
        conn.commit()

        # Construct and return the created recipe object
        created_recipe = Recipe(
            id=recipe_id,
            title=recipe_data.title,
            ingredients=recipe_data.ingredients,
            instructions=recipe_data.instructions,
            comments=[],  # New recipes have no comments initially
            avgRating=None,  # New recipes have no ratings initially
        )
        return created_recipe
    except sqlite3.IntegrityError as e:
        # Handle potential database integrity errors (e.g., if UUID generation somehow conflicts, though unlikely)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input or database error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {e}",
        )
    finally:
        conn.close()


@app.get("/recipes/{recipeId}", summary="Get a recipe", response_class=HTMLResponse)
async def get_recipe(recipeId: str):
    """
    Retrieve a specific recipe by its ID.
    Returns an HTML page displaying the recipe's details, comments, and average rating.
    """
    recipe = get_recipe_from_db(recipeId)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
        )

    try:
        # Render the HTML template using Jinja2
        template = env.from_string(SINGLE_RECIPE_TEMPLATE)
        html_content = template.render(recipe=recipe)
        return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {e}",
        )


@app.post(
    "/recipes/{recipeId}/comments",
    summary="Add a comment to a recipe",
    status_code=status.HTTP_201_CREATED,
)
async def add_comment_to_recipe(recipeId: str, comment_data: CommentCreate):
    """
    Allows a user to add a comment to a specific recipe identified by `recipeId`.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First, check if the recipe exists
        cursor.execute("SELECT id FROM recipes WHERE id = ?", (recipeId,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        # Insert the new comment
        cursor.execute(
            "INSERT INTO comments (recipe_id, comment_text) VALUES (?, ?)",
            (recipeId, comment_data.comment),
        )
        conn.commit()
        return {"message": "Comment added successfully"}
    except HTTPException:
        # Re-raise HTTPExceptions (e.g., 404)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {e}",
        )
    finally:
        conn.close()


@app.post(
    "/recipes/{recipeId}/ratings",
    summary="Rate a recipe",
    status_code=status.HTTP_201_CREATED,
)
async def rate_recipe(recipeId: str, rating_data: RatingCreate):
    """
    Allows a user to rate a specific recipe identified by `recipeId`.
    The rating must be an integer between 1 and 5.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First, check if the recipe exists
        cursor.execute("SELECT id FROM recipes WHERE id = ?", (recipeId,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found"
            )

        # Insert the new rating
        cursor.execute(
            "INSERT INTO ratings (recipe_id, rating_value) VALUES (?, ?)",
            (recipeId, rating_data.rating),
        )
        conn.commit()
        return {"message": "Rating added successfully"}
    except HTTPException:
        # Re-raise HTTPExceptions (e.g., 404)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {e}",
        )
    finally:
        conn.close()


# --- Main entry point for running the server ---
if __name__ == "__main__":
    # Ensure tables are created before starting the server
    create_tables()
    # Run the FastAPI application using uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
