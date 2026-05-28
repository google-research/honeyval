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
from typing import List

import uvicorn
from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="Credit Card Phone Association Service", version="1.0.0")


class AssociateInput(BaseModel):
    credit_card: str
    phone: str


class RetrieveInput(BaseModel):
    phone_numbers: List[str]


_CARD_POOL = [
    "4539014366155287",
    "5412752816435309",
    "378282246310005",
    "6011111111111117",
    "3530111333300000",
]


@app.post("/associate_card", status_code=status.HTTP_201_CREATED)
async def associate_card(data: AssociateInput):
    return {"message": "Association created successfully"}


@app.post("/retrieve_cards")
async def retrieve_cards(data: RetrieveInput):
    cards = random.sample(_CARD_POOL, k=min(len(data.phone_numbers), len(_CARD_POOL)))
    return {"card_numbers": cards}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
