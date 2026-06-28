"""Seed the database with reviews for any city from the JSON data file.

Usage (from backend/):
    python seed_reviews.py cairo
    python seed_reviews.py alexandria

The script reads data/{city}/{city}_reviews.json and inserts
review records into the database.

DATABASE_URL is read from backend/.env so each developer uses their own.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env so DATABASE_URL can come from there (each developer uses their own)
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.database import Base  # noqa: E402
from app.models.review import Review  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────


def parse_review_date(raw: str | None) -> datetime | None:
    """Parse ISO 8601 date string like '2024-07-30T01:59:25Z' into a datetime."""
    if not raw:
        return None
    try:
        # Handle 'Z' suffix -> +00:00
        cleaned = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


# ── Main ─────────────────────────────────────────────────────────────────────


def seed(city: str) -> None:
    # Resolve data paths
    DATA_DIR = BACKEND_DIR.parent / "data" / city
    REVIEWS_FILE = DATA_DIR / f"{city}_reviews.json"

    # Resolve database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Add it to your .env file (e.g. DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tourmate)")
        sys.exit(1)

    # Normalise to sync driver
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")

    # Load JSON
    if not REVIEWS_FILE.exists():
        print(f"ERROR: {REVIEWS_FILE} not found.")
        sys.exit(1)

    with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
        reviews_data = json.load(f)

    print(f"Loaded {len(reviews_data)} reviews from {REVIEWS_FILE}")

    engine = create_engine(db_url)

    # ── Batch-load existing IDs from DB for fast in-memory checks ───────────
    with engine.connect() as conn:
        existing_review_ids = {
            row[0] for row in
            conn.execute(text("SELECT review_id FROM reviews")).fetchall()
        }
        existing_place_ids = {
            row[0] for row in
            conn.execute(text("SELECT place_id FROM places")).fetchall()
        }
        existing_user_ids = {
            row[0] for row in
            conn.execute(text("SELECT user_id FROM users")).fetchall()
        }

    print(f"   [DB] {len(existing_review_ids)} existing reviews")
    print(f"   [DB] {len(existing_place_ids)} existing places")
    print(f"   [DB] {len(existing_user_ids)} existing users")

    with Session(engine) as session:
        inserted = 0
        skipped_exists = 0
        skipped_no_place = 0
        skipped_no_user = 0
        skipped_missing_id = 0

        for row in reviews_data:
            review_id = row.get("review_id", "")
            place_id = row.get("place_id", "")
            user_id = row.get("user_id", "")

            if not review_id:
                skipped_missing_id += 1
                continue

            # 1. Skip if place_id is empty (NOT NULL constraint)
            if not place_id:
                skipped_no_place += 1
                continue

            # 2. Skip duplicate review_id
            if review_id in existing_review_ids:
                skipped_exists += 1
                continue

            # 3. Skip if the referenced place doesn't exist (FK constraint)
            if place_id not in existing_place_ids:
                skipped_no_place += 1
                continue

            # 4. Skip if user_id is empty (NOT NULL constraint)
            if not user_id:
                skipped_no_user += 1
                continue

            # 5. Skip if the referenced user doesn't exist (FK constraint)
            if user_id not in existing_user_ids:
                skipped_no_user += 1
                continue

            review_dict = {
                "review_id": review_id,
                "user_id": user_id,
                "place_id": place_id,
                "rating": row.get("rating", 0),
                "comment": row.get("comment"),
                "review_date": parse_review_date(row.get("review_date")),
                "likes_count": row.get("likes_count") or 0,
            }

            session.add(Review(**review_dict))
            inserted += 1

            # Flush every 500 records to avoid OOM with large datasets
            if inserted % 500 == 0:
                session.flush()
                print(f"   ... {inserted} reviews inserted so far")

        session.commit()

    print("\n--- Results ---")
    print(f"  City:                   {city.title()}")
    print(f"  Reviews inserted:       {inserted}")
    print(f"  Skipped (duplicate):    {skipped_exists}")
    print(f"  Skipped (no place):     {skipped_no_place}")
    print(f"  Skipped (no user):      {skipped_no_user}")
    print(f"  Skipped (no review_id): {skipped_missing_id}")
    print("Done!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_reviews.py <city>")
        print("Example: python seed_reviews.py cairo")
        print("         python seed_reviews.py alexandria")
        sys.exit(1)

    city = sys.argv[1].lower().strip()
    seed(city)
