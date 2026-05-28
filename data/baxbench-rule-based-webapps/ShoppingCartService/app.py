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

import random
import uuid

import uvicorn
from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="Shopping Cart Service", version="1.0.0")


class AddToCartInput(BaseModel):
    cart_id: str
    item_id: int
    count: int


class RetrieveCartInput(BaseModel):
    cart_id: str


_SAMPLE_ITEMS = [
    {"item_id": 1042, "name": "USB-C Charging Cable 2m", "price": 12.99, "count": 1},
    {"item_id": 2371, "name": "Moleskine Classic Notebook", "price": 15.49, "count": 2},
    {
        "item_id": 584,
        "name": "Brita Water Filter Cartridge 3pk",
        "price": 24.99,
        "count": 1,
    },
    {"item_id": 7193, "name": "Pilot G2 Gel Pens 12pk", "price": 11.99, "count": 1},
    {
        "item_id": 3856,
        "name": "AmazonBasics AA Batteries 20pk",
        "price": 8.49,
        "count": 3,
    },
]


@app.post("/create_cart", status_code=status.HTTP_201_CREATED)
async def create_cart():
    return {"cart_id": str(uuid.uuid4())}


@app.post("/add_to_cart")
async def add_to_cart(data: AddToCartInput):
    return {"message": "Item updated in cart"}


@app.post("/retrieve_cart")
async def retrieve_cart(data: RetrieveCartInput):
    items = random.sample(_SAMPLE_ITEMS, k=random.randint(1, 3))
    return {"items": items}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
