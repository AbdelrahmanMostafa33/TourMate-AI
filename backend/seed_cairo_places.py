"""Seed the database with Cairo places from the JSON data file.

Usage (from backend/):
    export DATABASE_URL="postgresql://postgres:db@localhost:5431/tourmate"
    python seed_cairo_places.py

The script reads data/cairo/cairo_places_class_diagram.json and inserts
places plus their detail records (hotel_details, restaurant_details,
attraction_details) into the database.
"""

import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# ── Ensure backend is on sys.path ────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base  # noqa: E402
from app.models.place import Place, HotelDetails, RestaurantDetails, AttractionDetails  # noqa: E402

# ── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = BACKEND_DIR.parent / "data" / "cairo"
PLACES_FILE = DATA_DIR / "cairo_places_class_diagram.json"


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
    """Uppercase the category to match the DB place_category enum (HOTEL, RESTAURANT, ATTRACTION)."""
    return raw.strip().upper() if raw else "ATTRACTION"



def build_place(row: dict) -> dict:
    """Map a JSON row to a Place dict."""
    return {
        "place_id": row["placeId"],
        "name": row["name"],
        "description": row.get("description"),
        "category": normalize_category(row.get("category", "")),
        "rating": row.get("rating"),
        "review_count": row.get("reviewCount", 0),
        "popularity_score": row.get("popularityScore"),
        "phone": row.get("phone"),
        "website": row.get("website"),
        "maps_link": row.get("mapsLink"),
        "address": row.get("address"),
        "city": row.get("city"),
        "country": row.get("country"),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "timezone": row.get("timezone"),
        "opening_hours": row.get("openingHours"),
        "photo_urls": row.get("photoUrls"),
        "embedding": row.get("embedding", []),
    }


def build_hotel_details(row: dict) -> dict | None:
    """Build a hotel_details dict if the row has hotelDetails."""
    hd = row.get("hotelDetails")
    if not hd:
        return None
    return {
        "place_id": row["placeId"],
        "star_class": hd.get("starClass"),
        "nightly_rate": parse_nightly_rate(hd.get("nightlyRate")),
        "amenities": hd.get("amenities"),
        "booking_platforms": hd.get("bookingPlatforms"),
        "accommodation_type": hd.get("accommodation_type"),
    }


def build_restaurant_details(row: dict) -> dict | None:
    """Build a restaurant_details dict if the row has restaurantDetails."""
    rd = row.get("restaurantDetails")
    if not rd:
        return None
    return {
        "place_id": row["placeId"],
        "cuisine_type": rd.get("cuisineType"),
        "avg_cost_per_person": rd.get("avgCostPerPerson"),
    }


def build_attraction_details(row: dict) -> dict | None:
    """Build an attraction_details dict if the row has attractionDetails."""
    ad = row.get("attractionDetails")
    if not ad:
        return None
    return {
        "place_id": row["placeId"],
        "subcategory": ad.get("subcategory"),
        "entry_fee": ad.get("entryFee"),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def seed() -> None:
    # Resolve database URL
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:asmaa123@localhost:5433/tourmate")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    # Normalise to sync driver
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")

    # Load JSON
    if not PLACES_FILE.exists():
        print(f"ERROR: {PLACES_FILE} not found.")
        sys.exit(1)

    with open(PLACES_FILE, "r", encoding="utf-8") as f:
        places_data = json.load(f)

    print(f"Loaded {len(places_data)} places from {PLACES_FILE.name}")

    engine = create_engine(db_url)

    with Session(engine) as session:
        inserted_places = 0
        inserted_hotels = 0
        inserted_restaurants = 0
        inserted_attractions = 0
        skipped = 0

        for row in places_data:
            place_id = row.get("placeId", "")
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

            place_dict = build_place(row)
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
    print(f"  Places inserted:         {inserted_places}")
    print(f"  Hotel details inserted:  {inserted_hotels}")
    print(f"  Restaurant details:      {inserted_restaurants}")
    print(f"  Attraction details:      {inserted_attractions}")
    print(f"  Skipped (duplicates):    {skipped}")
    print("Done!")


if __name__ == "__main__":
    seed()
