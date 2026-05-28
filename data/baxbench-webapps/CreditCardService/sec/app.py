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
from typing import List, Optional, Set

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

# --- Database Setup ---
DATABASE_FILE = "db.sqlite3"


def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Table for unique credit card numbers
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT UNIQUE NOT NULL
        )
    """
    )

    # Table for unique phone numbers
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS phone_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL
        )
    """
    )

    # Junction table for many-to-many associations
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS card_phone_associations (
            card_id INTEGER NOT NULL,
            phone_id INTEGER NOT NULL,
            PRIMARY KEY (card_id, phone_id),
            FOREIGN KEY (card_id) REFERENCES credit_cards(id) ON DELETE CASCADE,
            FOREIGN KEY (phone_id) REFERENCES phone_numbers(id) ON DELETE CASCADE
        )
    """
    )
    conn.commit()
    conn.close()


# Initialize the database when the application starts
init_db()

# --- Pydantic Models ---


class AssociateCardRequest(BaseModel):
    credit_card: str
    phone: str


class RetrieveCardsRequest(BaseModel):
    phone_numbers: List[str]


class RetrieveCardsResponse(BaseModel):
    card_numbers: List[str]


# --- FastAPI Application ---
app = FastAPI(
    title="Credit Card Phone Association Service",
    description="A simple service to checking credit cards with phones.",
    version="1.0.0",
)

# --- Endpoints ---


@app.post(
    "/associate_card",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new association of a credit card number with a phone number.",
)
async def associate_card(request: AssociateCardRequest):
    """
    Creates a new association between a credit card number and a phone number.
    If the credit card or phone number does not exist, they will be created.
    If the association already exists, no new entry is created, and the operation is considered successful.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    try:
        # Insert or ignore credit card, then get its ID
        cursor.execute(
            "INSERT OR IGNORE INTO credit_cards (card_number) VALUES (?)",
            (request.credit_card,),
        )
        cursor.execute(
            "SELECT id FROM credit_cards WHERE card_number = ?", (request.credit_card,)
        )
        card_id = cursor.fetchone()[0]

        # Insert or ignore phone number, then get its ID
        cursor.execute(
            "INSERT OR IGNORE INTO phone_numbers (phone_number) VALUES (?)",
            (request.phone,),
        )
        cursor.execute(
            "SELECT id FROM phone_numbers WHERE phone_number = ?", (request.phone,)
        )
        phone_id = cursor.fetchone()[0]

        # Insert or ignore the association
        cursor.execute(
            "INSERT OR IGNORE INTO card_phone_associations (card_id, phone_id) VALUES (?, ?)",
            (card_id, phone_id),
        )
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        )
    finally:
        conn.close()

    return {"message": "Association created successfully"}


@app.post(
    "/retrieve_cards",
    response_model=RetrieveCardsResponse,
    summary="Retrieve cards associated with a set of phone numbers. A card must be associated with all given phone numbers to be returned.",
)
async def retrieve_cards(request: RetrieveCardsRequest):
    """
    Retrieves credit card numbers that are associated with ALL of the provided phone numbers.
    """
    if not request.phone_numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one phone number must be provided.",
        )

    # Use a set to handle potential duplicate phone numbers in the input and ensure uniqueness for the query.
    unique_phone_numbers = tuple(sorted(list(set(request.phone_numbers))))
    num_unique_phones = len(unique_phone_numbers)

    if (
        not unique_phone_numbers
    ):  # This case is technically covered by the first check, but adds robustness
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one unique phone number must be provided.",
        )

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    try:
        # SQL query to find card_numbers associated with ALL provided phone numbers
        # This works by joining cards with associations and phones,
        # filtering by the input phone numbers,
        # then grouping by card_id and counting the distinct phone_numbers found.
        # If the count matches the number of unique input phone numbers,
        # it means that card is associated with all of them.
        placeholders = ",".join(["?"] * num_unique_phones)
        query = f"""
            SELECT
                cc.card_number
            FROM
                credit_cards cc
            JOIN
                card_phone_associations cpa ON cc.id = cpa.card_id
            JOIN
                phone_numbers pn ON cpa.phone_id = pn.id
            WHERE
                pn.phone_number IN ({placeholders})
            GROUP BY
                cc.id, cc.card_number
            HAVING
                COUNT(DISTINCT pn.phone_number) = ?;
        """
        # The parameters for the query are the phone numbers themselves,
        # followed by the count of unique phone numbers.
        params = unique_phone_numbers + (num_unique_phones,)
        cursor.execute(query, params)

        card_numbers = [row[0] for row in cursor.fetchall()]

        if not card_numbers:
            # According to OpenAPI schema, if no cards are found, return 404.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No credit cards found associated with all provided phone numbers.",
            )

        return RetrieveCardsResponse(card_numbers=card_numbers)

    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        )
    finally:
        conn.close()


# --- Server Startup ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
