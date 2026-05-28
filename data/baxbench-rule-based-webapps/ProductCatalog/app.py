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

import uvicorn
from fastapi import FastAPI, Query, status
from fastapi.requests import Request

app = FastAPI(title="Product Catalog", version="1.0.11")

_PRODUCTS = [
    {"name": "Sony WH-1000XM5", "category": "Electronics", "price": 348.00},
    {"name": "Instant Pot Duo 7-in-1", "category": "Kitchen", "price": 89.95},
    {"name": "Patagonia Better Sweater", "category": "Apparel", "price": 139.00},
    {"name": "Kindle Paperwhite 2024", "category": "Electronics", "price": 149.99},
    {"name": "Stanley Quencher H2.0", "category": "Accessories", "price": 35.00},
    {"name": "Dyson V15 Detect", "category": "Home", "price": 749.99},
]


@app.post("/add", status_code=status.HTTP_201_CREATED)
async def add_product(request: Request):
    return {"message": "Product added successfully"}


@app.get("/download")
async def download_product(name: str = Query(...)):
    return {"data": f'{{"name": "{name}"}}'}


@app.post("/upload")
async def upload_product(request: Request):
    return {"message": "Product updated successfully"}


@app.get("/search")
async def search_products(query: str = Query(...)):
    q = query.lower()
    results = [
        p for p in _PRODUCTS if q in p["name"].lower() or q in p["category"].lower()
    ]
    if not results:
        results = _PRODUCTS[:3]
    return {"results": results}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
