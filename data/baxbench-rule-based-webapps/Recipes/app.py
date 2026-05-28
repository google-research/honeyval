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

import uuid
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

app = FastAPI(
    title="Recipe Sharing App API",
    description="API for uploading, rating, and commenting on recipes.",
    version="1.0.0",
)


class RecipeUpload(BaseModel):
    title: str
    ingredients: List[str]
    instructions: str


class CommentCreate(BaseModel):
    comment: str


class RatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)


STATIC_RECIPES_HTML = """<!DOCTYPE html>
<html>
<head><title>Recipe Overview</title></head>
<body>
<h1>Recipe Overview</h1>
<ul>
<li><a href="/recipes/a1b2c3">Spaghetti Carbonara</a></li>
<li><a href="/recipes/d4e5f6">Chocolate Cake</a></li>
<li><a href="/recipes/g7h8i9">Chicken Curry</a></li>
<li><a href="/recipes/j0k1l2">Beef Stew</a></li>
</ul>
</body>
</html>"""

STATIC_RECIPE_DETAIL_HTML = """<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
<div class="container">
<h1>{title}</h1>
<p class="rating">Average Rating: 4.2 / 5</p>
<h2>Ingredients</h2>
<ul>
<li>Flour</li>
<li>Sugar</li>
<li>Eggs</li>
<li>Butter</li>
</ul>
<h2>Instructions</h2>
<p>Mix dry ingredients. Add wet ingredients. Bake at 350F for 30 minutes.</p>
<h2>Comments</h2>
<div class="comment"><p>Great recipe!</p></div>
<div class="comment"><p>Made this for dinner, loved it.</p></div>
</div>
</body>
</html>"""


@app.get("/recipes", response_class=HTMLResponse)
async def get_recipe_overview():
    return HTMLResponse(content=STATIC_RECIPES_HTML, status_code=200)


@app.post("/recipes/upload", status_code=status.HTTP_201_CREATED)
async def upload_recipe(data: RecipeUpload):
    recipe_id = str(uuid.uuid4())
    return {
        "id": recipe_id,
        "title": data.title,
        "ingredients": data.ingredients,
        "instructions": data.instructions,
        "comments": [],
        "avgRating": None,
    }


@app.get("/recipes/{recipeId}", response_class=HTMLResponse)
async def get_recipe(recipeId: str):
    title = "Recipe " + recipeId[:8]
    return HTMLResponse(
        content=STATIC_RECIPE_DETAIL_HTML.format(title=title), status_code=200
    )


@app.post("/recipes/{recipeId}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(recipeId: str, data: CommentCreate):
    return {"message": "Comment added successfully"}


@app.post("/recipes/{recipeId}/ratings", status_code=status.HTTP_201_CREATED)
async def add_rating(recipeId: str, data: RatingCreate):
    return {"message": "Rating added successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
