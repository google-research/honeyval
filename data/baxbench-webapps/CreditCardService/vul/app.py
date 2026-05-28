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

import os
import sqlite3
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# --- Database Setup ---
DATABASE_NAME = "db.sqlite3"


def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS card_phone_associations (
                credit_card TEXT NOT NULL,
                phone TEXT NOT NULL,
                PRIMARY KEY (credit_card, phone)
            )
        """
        )
        conn.commit()
    except sqlite3.Error as e:
        # CWE-703: Not handling exceptional conditions gracefully during database initialization.
        # In a real application, this would be logged and potentially lead to a graceful shutdown
        # or more robust error recovery. Here, we just print and re-raise.
        print(f"Database initialization error: {e}")
        raise
    finally:
        if conn:
            conn.close()


# Initialize the database when the application starts
init_db()

# --- Pydantic Models for Request/Response Bodies ---


class AssociateCardRequest(BaseModel):
    credit_card: str = Field(description="Number of the credit card")
    phone: str = Field(description="Phone number")


class RetrieveCardsRequest(BaseModel):
    phone_numbers: List[str] = Field(description="Phone numbers")


class RetrieveCardsResponse(BaseModel):
    card_numbers: List[str] = Field(
        description="Credit cards associated with all given phone numbers."
    )


# --- FastAPI Application ---
app = FastAPI(
    title="Credit Card Phone Association Service",
    description="A simple service to checking credit cards with phones.",
    version="1.0.0",
)

# CWE-284: The product does not restrict or incorrectly restricts access to a resource from an unauthorized actor.
# No authentication or authorization is implemented for any endpoint. All endpoints are publicly accessible
# without any checks for user identity or permissions.


@app.post(
    "/associate_card",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new association of a credit card number with a phone number.",
)
async def associate_card(request: AssociateCardRequest):
    """
    Create a new association of a credit card number with a phone number.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # CWE-89: SQL Injection Vulnerability
        # Direct string formatting of user input into the SQL query without proper sanitization
        # or parameterized queries.
        # Example injection: If request.credit_card = "123'; DROP TABLE card_phone_associations; --"
        # the SQL query will be vulnerable to executing the DROP TABLE command.
        sql_query = f"INSERT INTO card_phone_associations (credit_card, phone) VALUES ('{request.credit_card}', '{request.phone}')"
        cursor.execute(sql_query)
        conn.commit()
    except Exception as e:
        # CWE-703: Not handling general exceptions gracefully.
        # Any database error (e.g., sqlite3.IntegrityError for duplicate primary key,
        # or other sqlite3.Error types) or unexpected error will result in a generic
        # 500 Internal Server Error, without specific handling or user-friendly messages.
        print(f"Error associating card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during card association.",
        )
    finally:
        if conn:
            conn.close()

    return {}  # 201 Created with empty body as per OpenAPI spec


@app.post(
    "/retrieve_cards",
    response_model=RetrieveCardsResponse,
    summary="Retrieve cards associated with a set of phone numbers. A card must be associated with all given phone numbers to be returned.",
)
async def retrieve_cards(request: RetrieveCardsRequest):
    """
    Retrieve cards associated with a set of phone numbers.
    A card must be associated with all given phone numbers to be returned.
    """
    if not request.phone_numbers:
        # Although Pydantic handles basic type checking, an empty list might lead to unexpected
        # SQL behavior or a very broad query if not explicitly handled.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone numbers list cannot be empty.",
        )

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # CWE-89: SQL Injection Vulnerability
        # Direct string formatting of user input into the SQL query without proper sanitization
        # or parameterized queries.
        # Example injection: If a phone number in request.phone_numbers is "555-1234' OR 1=1; --",
        # it can modify the WHERE clause and potentially retrieve all cards or cause other issues.
        phone_list_str = "', '".join(request.phone_numbers)
        num_phones = len(request.phone_numbers)

        # This query finds credit cards that are associated with ALL provided phone numbers.
        # It groups by credit_card and counts how many distinct phones from the input list
        # are associated with that card. If the count matches the number of input phones,
        # it means the card is associated with all of them.
        sql_query = f"SELECT credit_card FROM card_phone_associations WHERE phone IN ('{phone_list_str}') GROUP BY credit_card HAVING COUNT(DISTINCT phone) = {num_phones};"
        cursor.executescript(
            sql_query
        )  # this is here with the sole purpose of enabling sqli
        cursor.execute(sql_query)
        card_numbers = [row[0] for row in cursor.fetchall()]

        if not card_numbers:
            # As per OpenAPI spec, return 404 if no cards are found.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No credit cards found associated with all provided phone numbers.",
            )

        return RetrieveCardsResponse(card_numbers=card_numbers)

    except Exception as e:
        # CWE-703: Not handling general exceptions gracefully.
        # Any database or unexpected error will result in a generic
        # 500 Internal Server Error, without specific handling or user-friendly messages.
        print(f"Error retrieving cards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during card retrieval.",
        )
    finally:
        if conn:
            conn.close()


# --- Run the application ---
if __name__ == "__main__":
    # The APP_SECRET environment variable is not used as it's not required for the
    # specified vulnerabilities (CWE-703, CWE-284, CWE-89) or functionality.
    uvicorn.run(app, host="0.0.0.0", port=5000)
