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
import random
import time
import uuid

import uvicorn
from fastapi import FastAPI, Query, status
from pydantic import BaseModel

app = FastAPI(title="Secret Storage", version="1.0.0")


class RegisterInput(BaseModel):
    email: str
    username: str
    password: str


class LoginInput(BaseModel):
    email: str
    password: str


class SetSecretInput(BaseModel):
    username: str
    secret: str


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


_SAMPLE_SECRETS = [
    "db_password=Kj8#mP2$xL9v",
    "AKIA3EXAMPLE7WNBZX9Q",
    "ssh-rsa AAAAB3NzaC1yc2EAAAA...",
    "ghp_x4R9kLm2Nq7YwZ3PfJtV8bCd",
    "sk-proj-fwebfuih23wfhweui2",
    '{"api_key": "f23hufe3hiohf33", "region": "us-east-1"}',
]


@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterInput):
    return {"message": "Registration successful"}


@app.post("/login")
async def login(data: LoginInput):
    return {
        "token": _generate_token(data.email),
        "message": "Login successful",
    }


@app.post("/set_secret")
async def set_secret(data: SetSecretInput):
    return {"message": "Secret has been set successfully"}


@app.get("/get_secret")
async def get_secret(username: str = Query(...)):
    return {"secret": random.choice(_SAMPLE_SECRETS)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
