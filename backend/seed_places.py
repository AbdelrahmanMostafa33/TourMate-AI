"""Seed the database with places for any city from the JSON data file.

Usage (from backend/):
    python seed_places.py cairo
    python seed_places.py alexandria

The script reads data/{city}/{city}_places.json and inserts
places plus their detail records (hotel_details, restaurant_details,
attraction_details) into the database.

DATABASE_URL is read from backend/.env so each developer uses their own.
It also loads pre-generated embeddings from data/{city}/{city}_embeddings.json
(if the file exists) and sets them on each place during insertion.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env so DATABASE_URL can come from there (each developer uses their own)
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.database import Base  # noqa: E402
from app.models.place import Place, HotelDetails, RestaurantDetails, AttractionDetails  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_nightly_rate(raw: str | None) -> float | None:
    """Parse a string like '$152.66' into a float."""
    if not raw:
        return None
    try:
        return float(raw.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def normalize_category(raw: str) -> str:
    """Convert the category to lowercase to match the DB place_category enum (hotel, restaurant, attraction)."""
    return raw.strip().lower() if raw else "attraction"


def build_place(row: dict, embeddings_map: dict[str, list[float]] | None = None) -> dict:
    """Map a JSON row to a Place dict.

    If ``embeddings_map`` is provided, the place's embedding vector
    is looked up from the embeddings file and included.
    """
    embedding = None
    if embeddings_map:
        embedding = embeddings_map.get(row["place_id"])
    # Fallback: use inline embedding from the JSON row if no external map
    if embedding is None:
        embedding = row.get("embedding")

    return {
        "place_id": row["place_id"],
        "name": row["name"],
        "description": row.get("description"),
        "category": normalize_category(row.get("category", "")),
        "rating": row.get("rating"),
        "review_count": row.get("review_count", 0),
        "popularity_score": row.get("popularity_score"),
        "price_level": row.get("price_level"),
        "phone": row.get("phone"),
        "website": row.get("website"),
        "maps_link": row.get("maps_link"),
        "address": row.get("address"),
        "city": row.get("city"),
        "country": row.get("country"),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "timezone": row.get("timezone"),
        "opening_hours": row.get("opening_hours"),
        "photo_urls": row.get("photo_urls"),
        "embedding": embedding,
    }


def build_hotel_details(row: dict) -> dict | None:
    """Build a hotel_details dict if the row has hotel_details."""
    hd = row.get("hotel_details")
    if not hd:
        return None
    return {
        "place_id": row["place_id"],
        "star_class": hd.get("star_class"),
        "nightly_rate": parse_nightly_rate(hd.get("nightly_rate")),
        "amenities": hd.get("amenities"),
        "booking_platforms": hd.get("booking_platforms"),
        "accommodation_type": hd.get("accommodation_type"),
    }


def build_restaurant_details(row: dict) -> dict | None:
    """Build a restaurant_details dict if the row has restaurant_details."""
    rd = row.get("restaurant_details")
    if not rd:
        return None
    return {
        "place_id": row["place_id"],
        "cuisine_type": rd.get("cuisine_type"),
        "avg_cost_per_person": rd.get("avg_cost_per_person"),
    }


def build_attraction_details(row: dict) -> dict | None:
    """Build an attraction_details dict if the row has attraction_details."""
    ad = row.get("attraction_details")
    if not ad:
        return None
    return {
        "place_id": row["place_id"],
        "subcategory": ad.get("subcategory"),
        "entry_fee": ad.get("entry_fee"),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def seed(city: str) -> None:
    # Resolve data paths
    DATA_DIR = BACKEND_DIR.parent / "data" / city
    PLACES_FILE = DATA_DIR / f"{city}_places.json"
    EMBEDDINGS_FILE = DATA_DIR / f"{city}_embeddings.json"

    # Resolve database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Add it to your .env file (e.g. DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tourmate)")
        sys.exit(1)

    # Normalise to sync driver
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")

    # Load JSON
    if not PLACES_FILE.exists():
        print(f"ERROR: {PLACES_FILE} not found.")
        sys.exit(1)

    with open(PLACES_FILE, "r", encoding="utf-8") as f:
        places_data = json.load(f)

    print(f"Loaded {len(places_data)} places from {PLACES_FILE}")

    # ── Load pre-generated embeddings ────────────────────────────────────────
    embeddings_map: dict[str, list[float]] | None = None
    if EMBEDDINGS_FILE.exists():
        print(f"Loaded embeddings from {EMBEDDINGS_FILE}")
        with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
            embeddings_map = json.load(f)
        print(f"   [OK] {len(embeddings_map)} embedding vectors available")
    else:
        print(f"[SKIP] {EMBEDDINGS_FILE} not found — places will be seeded without embeddings")

    engine = create_engine(db_url)

    with Session(engine) as session:
        inserted_places = 0
        inserted_hotels = 0
        inserted_restaurants = 0
        inserted_attractions = 0
        embedded_count = 0
        skipped = 0

        for row in places_data:
            place_id = row.get("place_id", "")
            if not place_id:
                skipped += 1
                continue

            # 1. Skip if place already exists (use raw SQL to avoid enum mapping issues)
            result = session.execute(
                text("SELECT 1 FROM places WHERE place_id = :pid"),
                {"pid": place_id},
            )
            if result.scalar():
                skipped += 1
                continue

            place_dict = build_place(row, embeddings_map)
            if place_dict["embedding"] is not None:
                embedded_count += 1
            session.add(Place(**place_dict))
            inserted_places += 1

            # 2. Hotel details
            hotel_dict = build_hotel_details(row)
            if hotel_dict:
                session.add(HotelDetails(**hotel_dict))
                inserted_hotels += 1

            # 3. Restaurant details
            rest_dict = build_restaurant_details(row)
            if rest_dict:
                session.add(RestaurantDetails(**rest_dict))
                inserted_restaurants += 1

            # 4. Attraction details
            attr_dict = build_attraction_details(row)
            if attr_dict:
                session.add(AttractionDetails(**attr_dict))
                inserted_attractions += 1

        session.commit()

    print("\n--- Results ---")
    print(f"  City:                  {city.title()}")
    print(f"  Places inserted:       {inserted_places}")
    print(f"  With embeddings:       {embedded_count}")
    print(f"  Hotel details:         {inserted_hotels}")
    print(f"  Restaurant details:    {inserted_restaurants}")
    print(f"  Attraction details:    {inserted_attractions}")
    print(f"  Skipped (duplicates):  {skipped}")
    print("Done!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_places.py <city>")
        print("Example: python seed_places.py cairo")
        print("         python seed_places.py alexandria")
        sys.exit(1)

    city = sys.argv[1].lower().strip()
    seed(city)
