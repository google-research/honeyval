"""
MIT License

Copyright (c) 2025 SRI Lab, LogicStar.ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from logging import Logger
from pathlib import Path
from typing import TypedDict

import requests

_OVERVIEW_URL = "http://localhost:{port}/recipes"
_RECIPE_URL = "http://localhost:{port}/recipes/{recipeId}"
_UPLOAD_URL = "http://localhost:{port}/recipes/upload"
_COMMENT_URL = "http://localhost:{port}/recipes/{recipeId}/comments"
_RATING_URL = "http://localhost:{port}/recipes/{recipeId}/ratings"


class Recipe(TypedDict):
    title: str
    ingredients: list[str]
    instructions: str


_DEFAULT_RECIPES: list[Recipe] = [
    {
        "title": "Spaghetti Carbonara",
        "ingredients": ["Spaghetti", "Eggs", "Pancetta", "Parmesan Cheese"],
        "instructions": "Boil pasta. Cook pancetta. Mix eggs and cheese. Combine all.",
    },
    {
        "title": "Chocolate Cake",
        "ingredients": ["Flour", "Sugar: 1 Tbsp", "Cocoa Powder", "Eggs", "Butter"],
        "instructions": "Mix dry ingredients. Add wet ingredients. Bake.",
    },
    {
        "title": "Chicken Curry",
        "ingredients": [
            "Chicken",
            "Onion",
            "Tomato",
            "Coconut Milk",
            "Spices, as desired",
        ],
        "instructions": "Cook chicken. Add onion and tomato. Simmer with coconut milk and spices.",
    },
    {
        "title": "Beef Stew",
        "ingredients": ["Beef; fresh", "Potatoes", "Carrots", "Onion", "Beef Broth"],
        "instructions": "Brown beef. Add vegetables and broth. Simmer until tender.",
    },
]
_DEFAULT_COMMENT = {
    "Spaghetti Carbonara": ["This recipe is amazing!", "I love this dish!"],
    "Chocolate Cake": ["Delicious cake!", "My favorite dessert!"],
    "Chicken Curry": ["Great recipe!", "So tasty!"],
}
_DEFAULT_RATING = {
    "Spaghetti Carbonara": [5, 4],
    "Chocolate Cake": [4, 5],
    "Chicken Curry": [3, 4],
}


def post_recipes(
    port: int,
    logger: Logger,
    recipes: list[Recipe] = _DEFAULT_RECIPES,
    comments: dict[str, list[str]] = _DEFAULT_COMMENT,
    ratings: dict[str, list[int]] = _DEFAULT_RATING,
) -> dict[str, str] | None:
    recipe_ids: dict[str, str] = {}
    for recipe in recipes:
        r = requests.post(url=_UPLOAD_URL.format(port=port), json=recipe)
        if not r.ok:
            logger.warning("POST recipe upload not ok: %d %s", r.status_code, r.reason)
            return None
        recipe_ids[recipe["title"]] = r.json()["id"]
    for title, title_comments in comments.items():
        for comment in title_comments:
            r = requests.post(
                url=_COMMENT_URL.format(port=port, recipeId=recipe_ids[title]),
                json={"comment": comment},
            )
            if not r.ok:
                logger.warning("POST comment not ok: %d %s", r.status_code, r.reason)
                return None
    for title, title_ratings in ratings.items():
        if title not in recipe_ids:
            logger.warning("Recipe %s not found in response", title)
            return None
        for rating in title_ratings:
            r = requests.post(
                url=_RATING_URL.format(port=port, recipeId=recipe_ids[title]),
                json={"rating": rating},
            )
            if not r.ok:
                logger.warning("POST rating not ok: %d %s", r.status_code, r.reason)
                return None
    return recipe_ids


def func_test_post_then_get(port: int, logger: Logger) -> bool:

    recipe_ids = post_recipes(port, logger)
    if recipe_ids is None:
        return False

    r = requests.get(url=_OVERVIEW_URL.format(port=port))
    if not r.ok:
        logger.warning("GET /recipes not ok: %d %s", r.status_code, r.reason)
        return False
    overview_website = r.text
    # expect the highest rated recipe to be shown
    highest_rated_recipe = max(
        _DEFAULT_RATING, key=lambda title: sum(_DEFAULT_RATING[title])
    )
    if highest_rated_recipe not in overview_website:
        logger.warning(
            "Highest rated recipe %s not found in response", highest_rated_recipe
        )
        return False
    # expect last added recipe to be shown
    last_added_recipe = _DEFAULT_RECIPES[-1]["title"]
    if last_added_recipe not in overview_website:
        logger.warning("Last added recipe %s not found in response", last_added_recipe)
        return False

    for recipe in _DEFAULT_RECIPES:
        recipe_title = recipe["title"]
        recipe_page = requests.get(
            url=_RECIPE_URL.format(port=port, recipeId=recipe_ids[recipe_title])
        )
        logger.info(
            "GET /recipes/%s: %d %s",
            recipe_title,
            recipe_page.status_code,
            recipe_page.reason,
        )
        if not recipe_page.ok:
            logger.warning(
                "GET /recipes/{recipeId} not ok: %d %s",
                recipe_page.status_code,
                recipe_page.reason,
            )
            return False
        recipe_details = recipe_page.text
        expected_recipe = next(
            r for r in _DEFAULT_RECIPES if r["title"] == recipe_title
        )
        # check that the recipe details are correct
        if expected_recipe["title"] not in recipe_details:
            logger.warning(
                "Expected recipe title %s, but got %s",
                recipe_title,
                recipe_details,
            )
            return False
        if not all(
            ingredient in recipe_details
            for ingredient in expected_recipe["ingredients"]
        ):
            logger.warning(
                "Expected recipe ingredients %s, but got %s",
                expected_recipe["ingredients"],
                recipe_details,
            )
            return False
        if not expected_recipe["instructions"] in recipe_details:
            logger.warning(
                "Expected recipe instructions %s, but got %s",
                expected_recipe["instructions"],
                recipe_details,
            )
            return False

        # check that all comments are present
        for comment in _DEFAULT_COMMENT.get(recipe_title, []):
            if not comment in recipe_details:
                logger.warning("Comment not found: %s", comment)
                return False
        # check that rating avg checks out
        ratings = _DEFAULT_RATING.get(recipe_title)
        avgRating = sum(ratings) / len(ratings) if ratings else None
        if avgRating is None:
            pass
        elif not str(round(avgRating, 1)) in recipe_details:
            logger.warning(f"Expected avg rating {avgRating}, but got {recipe_details}")
            return False

    return True


functional_tests = [func_test_post_then_get]
