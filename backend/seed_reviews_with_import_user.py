"""Seed all reviews using a single "google_import_user".

Creates the user if they don't exist, then inserts all reviews from all
4 cities (cairo, alexandria, luxor, aswan) mapping all google_user_*
IDs to this single user.

Usage:
    python seed_reviews_with_import_user.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.review import Review
from app.models.user import User

CITIES = ["cairo", "alexandria", "luxor", "aswan"]
IMPORT_USER_ID = "google_import_user"
DATA_DIR = BACKEND_DIR.parent / "data"


def parse_review_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        cleaned = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def ensure_import_user(session: Session) -> None:
    """Create the import user if they don't exist."""
    result = session.execute(
        text("SELECT 1 FROM users WHERE user_id = :uid"),
        {"uid": IMPORT_USER_ID},
    )
    if result.scalar():
        print(f"  [OK] User '{IMPORT_USER_ID}' already exists")
        return

    user = User(
        user_id=IMPORT_USER_ID,
        email="google_import@tourmate.ai",
        full_name="Google Import User",
        registration_date=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    print(f"  [OK] Created user '{IMPORT_USER_ID}'")


def load_existing_place_ids(session: Session) -> set[str]:
    rows = session.execute(text("SELECT place_id FROM places")).fetchall()
    return {row[0] for row in rows}


def seed_city(session: Session, city: str, existing_place_ids: set[str]) -> dict:
    """Seed reviews for one city. Returns counts."""
    file_path = DATA_DIR / city / f"{city}_reviews.json"
    if not file_path.exists():
        print(f"  [SKIP] {file_path} not found")
        return {"inserted": 0, "skipped_exists": 0, "skipped_no_place": 0, "skipped_no_user": 0, "skipped_missing_id": 0}

    with open(file_path, "r", encoding="utf-8") as f:
        reviews_data = json.load(f)

    print(f"  [LOAD] {len(reviews_data)} reviews from {file_path}")

    # Load existing review IDs
    existing_review_ids = {
        row[0]
        for row in session.execute(text("SELECT review_id FROM reviews")).fetchall()
    }
    print(f"  [DB] {len(existing_review_ids)} existing reviews")

    inserted = 0
    skipped_exists = 0
    skipped_no_place = 0
    skipped_missing_id = 0

    for row in reviews_data:
        review_id = row.get("review_id", "")
        place_id = row.get("place_id", "")

        if not review_id:
            skipped_missing_id += 1
            continue
        if not place_id:
            skipped_missing_id += 1
            continue
        if review_id in existing_review_ids:
            skipped_exists += 1
            continue
        if place_id not in existing_place_ids:
            skipped_no_place += 1
            continue

        review = Review(
            review_id=review_id,
            user_id=IMPORT_USER_ID,
            place_id=place_id,
            rating=row.get("rating") or 0,
            comment=row.get("comment"),
            review_date=parse_review_date(row.get("review_date")),
            likes_count=row.get("likes_count") or 0,
        )
        session.add(review)
        inserted += 1
        existing_review_ids.add(review_id)

        if inserted % 500 == 0:
            session.flush()
            print(f"    ... {inserted} reviews inserted so far")

    session.commit()

    return {
        "inserted": inserted,
        "skipped_exists": skipped_exists,
        "skipped_no_place": skipped_no_place,
        "skipped_missing_id": skipped_missing_id,
    }


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Add it to your .env file")
        sys.exit(1)

    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")
    engine = create_engine(db_url)

    with Session(engine) as session:
        print("=" * 60)
        print("STEP 1: Ensure import user exists")
        print("=" * 60)
        ensure_import_user(session)

        print("\n" + "=" * 60)
        print("STEP 2: Load existing place IDs")
        print("=" * 60)
        existing_place_ids = load_existing_place_ids(session)
        print(f"  [OK] {len(existing_place_ids)} places in database")

        print("\n" + "=" * 60)
        print("STEP 3: Seed reviews for all cities")
        print("=" * 60)
        totals = {"inserted": 0, "skipped_exists": 0, "skipped_no_place": 0, "skipped_missing_id": 0}

        for city in CITIES:
            print(f"\n--- {city.title()} ---")
            result = seed_city(session, city, existing_place_ids)
            for k in totals:
                totals[k] += result[k]

        print("\n" + "=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        print(f"  Reviews inserted:       {totals['inserted']}")
        print(f"  Skipped (duplicate):    {totals['skipped_exists']}")
        print(f"  Skipped (no place):     {totals['skipped_no_place']}")
        print(f"  Skipped (no review_id): {totals['skipped_missing_id']}")
        print("Done!")


if __name__ == "__main__":
    main()
