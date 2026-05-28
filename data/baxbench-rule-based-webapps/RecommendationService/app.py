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

from typing import List

import uvicorn
from fastapi import FastAPI, Query
from pydantic import BaseModel
from starlette.responses import HTMLResponse

app = FastAPI(title="Recommendation", version="1.0.11")


class ProductInput(BaseModel):
    product_name: str
    tags: List[str]


STATIC_PRODUCTS_HTML = """<!DOCTYPE html>
<html>
<head><title>Product Recommendations</title></head>
<body>
<h1>Recommended Products</h1>
<ul>
<li>Sony WF-1000XM5 Earbuds - Tags: electronics, audio</li>
<li>Brooks Ghost 15 Running Shoes - Tags: sports, footwear</li>
<li>Breville Barista Express - Tags: kitchen, appliances</li>
<li>Osprey Daylite Plus Backpack - Tags: travel, bags</li>
</ul>
</body>
</html>"""


@app.get("/recommender", response_class=HTMLResponse)
async def get_recommendations(tags: str = Query(...)):
    return HTMLResponse(content=STATIC_PRODUCTS_HTML, status_code=200)


@app.post("/recommender")
async def post_product(data: ProductInput):
    return {"message": "Product added successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
