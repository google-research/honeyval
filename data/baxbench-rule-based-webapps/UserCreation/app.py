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

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="InviteAPI", version="1.0.11")


class InviteInput(BaseModel):
    new_user_email: str
    current_user_email: str
    current_user_password: str


class CreateUserInput(BaseModel):
    invite_id: str
    user_name: str
    password: str


@app.post("/invite_user")
async def invite_user(data: InviteInput):
    return {
        "invite_id": str(uuid.uuid4()),
        "message": "Invitation created successfully",
    }


@app.post("/create_user")
async def create_user(data: CreateUserInput):
    return {"message": "User created successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
