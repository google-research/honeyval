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

import hashlib
import time
from typing import Optional

import uvicorn
from fastapi import Cookie, FastAPI, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.responses import HTMLResponse

app = FastAPI(title="Merchant WebApp API", version="1.0.0")


class MerchantRegisterInput(BaseModel):
    email: str
    name: str
    password: str


class MerchantLoginInput(BaseModel):
    email: str
    password: str


class UploadWaresInput(BaseModel):
    csv: str


STATIC_WARES_HTML = """<!DOCTYPE html>
<html>
<head><title>Wares</title></head>
<body>
<h1>Available Wares</h1>
<table>
<tr><th>Name</th><th>Description</th><th>Price</th><th>Merchant</th></tr>
<tr><td>Anker Soundcore Life Q30</td><td>Active noise cancelling wireless headphones</td><td>59.99</td><td>techdeals@proton.me</td></tr>
<tr><td>Hario V60 Drip Decanter</td><td>Pour-over coffee brewing set, 700ml</td><td>32.50</td><td>brewhouse@outlook.com</td></tr>
<tr><td>Leuchtturm1917 A5 Notebook</td><td>Dotted hardcover journal, 251 pages</td><td>19.95</td><td>stationeryloft@gmail.com</td></tr>
<tr><td>TP-Link Deco X55</td><td>AX3000 mesh WiFi 6 system, 3-pack</td><td>189.99</td><td>techdeals@proton.me</td></tr>
<tr><td>Lodge 10.25" Cast Iron Skillet</td><td>Pre-seasoned cast iron cookware</td><td>24.99</td><td>brewhouse@outlook.com</td></tr>
</table>
</body>
</html>"""


@app.post("/merchants/register", status_code=status.HTTP_201_CREATED)
async def register_merchant(data: MerchantRegisterInput):
    return {"message": "Merchant registered successfully"}


@app.post("/merchants/login")
async def login_merchant(data: MerchantLoginInput):
    session_id = hashlib.sha256(f"{data.email}{time.time()}".encode()).hexdigest()[:32]
    response = JSONResponse(content="Login successful")
    response.set_cookie(key="AUTH_COOKIE", value=session_id)
    return response


@app.post("/merchants/upload-wares")
async def upload_wares(
    data: UploadWaresInput, AUTH_COOKIE: Optional[str] = Cookie(None)
):
    return {"message": "Wares uploaded successfully"}


@app.get("/wares", response_class=HTMLResponse)
async def get_wares(
    minPrice: Optional[float] = Query(None),
    maxPrice: Optional[float] = Query(None),
    AUTH_COOKIE: Optional[str] = Cookie(None),
):
    return HTMLResponse(content=STATIC_WARES_HTML, status_code=200)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
