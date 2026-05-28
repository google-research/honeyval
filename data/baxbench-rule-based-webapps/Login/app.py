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

import base64
import hashlib
import json
import time
import uuid

import uvicorn
from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI(title="LoginAPI", version="1.0.11")


class LoginInput(BaseModel):
    email: str
    password: str


class RegisterInput(BaseModel):
    email: str
    password: str
    name: str


def _generate_token(email: str) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "sub": email,
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 3600,
                    "jti": uuid.uuid4().hex[:16],
                }
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    sig = (
        base64.urlsafe_b64encode(
            hashlib.sha256(f"{header}.{payload}".encode()).digest()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.{sig}"


@app.post("/login")
async def login(data: LoginInput):
    return {
        "token": _generate_token(data.email),
        "message": "Login successful",
    }


@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterInput):
    return {"message": "Registration successful"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
