"""
One-time enrichment script: match local hotel names → Expedia property IDs.

Reads all hotels from the database, searches for each one on the Expedia
Rapid API by city name, and stores the matching ``property_id`` in the
``booking_platforms`` JSON field of each hotel's ``hotel_details`` record.

The match is done by name similarity (case-insensitive substring match)
between the hotel name in your database and the property name returned
by Expedia.

Usage (from backend/):
    python scripts/enrich_hotel_expedia_ids.py
    python scripts/enrich_hotel_expedia_ids.py --city Cairo
    python scripts/enrich_hotel_expedia_ids.py --dry-run

Requires:
    - EXPEDIA_API_KEY and EXPEDIA_API_SECRET set in your .env file
    - A running database with seeded hotel data
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure backend/ is on the Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Fuzzy name matching threshold ─────────────────────────────────────────────
# If enough words from the DB hotel name appear in the Expedia property name,
# we consider it a match.  Higher = stricter.
_MIN_WORD_OVERLAP = 2


def _name_matches(db_name: str, expedia_name: str) -> bool:
    """Check if a DB hotel name matches an Expedia property name.

    Uses case-insensitive word overlap.  Short names (≤3 words) require
    a higher overlap ratio than longer names.
    """
    db_words = set(w.lower() for w in db_name.split() if len(w) > 1)
    exp_words = set(w.lower() for w in expedia_name.split() if len(w) > 1)

    if not db_words or not exp_words:
        return False

    overlap = db_words & exp_words
    if not overlap:
        return False

    # For short names, require most words to match
    if len(db_words) <= 3:
        return len(overlap) >= len(db_words) - 1

    return len(overlap) >= _MIN_WORD_OVERLAP


async def enrich_city(
    city: str,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Enrich all hotels in a given city with Expedia property IDs.

    Args:
        city:     City name (e.g. "Cairo", "Alexandria").
        dry_run:  If True, log matches but don't write to DB.
        force:    If True, re-match even if a hotel already has an Expedia ID.

    Returns:
        A dict with: ``city``, ``total_hotels``, ``matched``, ``failed``,
        ``skipped``.
    """
    from app.external.expedia_client import expedia_client
    from app.core.database import async_session
    from app.models.place import Place, HotelDetails
    from app.models.enums import PlaceCategory
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # ── Pick a date range for the search ──────────────────────────────────
    # The Expedia search API requires checkin/checkout dates.  We use a
    # generic future date so the search returns available properties.
    import datetime
    checkin = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    checkout = (datetime.date.today() + datetime.timedelta(days=32)).isoformat()

    # ── Load all hotels for this city ────────────────────────────────────
    async with async_session() as db:
        result = await db.execute(
            select(Place)
            .options(selectinload(Place.hotel_details))
            .where(
                Place.category == PlaceCategory.hotel,
                Place.city.ilike(city),
            )
        )
        hotels = list(result.scalars().all())

    logger.info(f"City: {city}")
    logger.info(f"Hotels found: {len(hotels)}")
    logger.info(f"Check-in: {checkin}, Check-out: {checkout}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")

    if not hotels:
        return {"city": city, "total_hotels": 0, "matched": 0, "failed": 0, "skipped": 0}

    # ── Search Expedia for hotels in this city ───────────────────────────
    logger.info("Searching Expedia for hotels in %s...", city)
    try:
        expedia_offers = await expedia_client.search_hotels(
            city=city,
            checkin=checkin,
            checkout=checkout,
            guests=2,
            max_results=50,
        )
    except ValueError as exc:
        logger.error(f"  [ERROR] Expedia search failed: {exc}")
        logger.error("  Skipping city. Check your API credentials.")
        return {"city": city, "total_hotels": len(hotels), "matched": 0, "failed": len(hotels), "skipped": 0}

    # Build a lookup: property name → property_id
    expedia_properties: list[dict] = []
    for offer in expedia_offers:
        # The offer structure can vary.  Try to extract name + id.
        prop_info = {
            "property_id": offer.get("property_id") or offer.get("id", ""),
            "name": offer.get("name") or offer.get("property_name", ""),
        }
        if prop_info["property_id"] and prop_info["name"]:
            expedia_properties.append(prop_info)

    logger.info(f"  Expedia returned {len(expedia_properties)} properties")
    logger.info("")

    # ── Match each local hotel to an Expedia property ────────────────────
    matched = 0
    failed = 0
    skipped = 0
    matches: list[dict] = []

    for hotel in hotels:
        hd = hotel.hotel_details
        if not hd:
            failed += 1
            continue

        # Check if already has an Expedia ID
        platforms = hd.booking_platforms or []
        existing_expedia = any(
            p.startswith("expedia:") for p in platforms
        )
        if existing_expedia and not force:
            skipped += 1
            continue

        # Try to match by name
        best_match = None
        best_score = 0

        for prop in expedia_properties:
            if _name_matches(hotel.name, prop["name"]):
                # Score by word overlap ratio
                db_words = set(w.lower() for w in hotel.name.split() if len(w) > 1)
                exp_words = set(w.lower() for w in prop["name"].split() if len(w) > 1)
                overlap_ratio = len(db_words & exp_words) / max(len(db_words), 1)
                if overlap_ratio > best_score:
                    best_score = overlap_ratio
                    best_match = prop

        if best_match:
            expedia_id = f"expedia:{best_match['property_id']}"
            matches.append({
                "place_id": hotel.place_id,
                "db_name": hotel.name,
                "expedia_name": best_match["name"],
                "expedia_id": expedia_id,
                "score": round(best_score, 2),
            })
            matched += 1

            if not dry_run:
                # Update the booking_platforms field
                platforms = hd.booking_platforms or []
                if expedia_id not in platforms:
                    platforms.append(expedia_id)
                    hd.booking_platforms = platforms
                    hd.place_id = hotel.place_id  # ensure FK is set
        else:
            failed += 1
            logger.info(f"  [NO MATCH] {hotel.name}")

    # ── Commit changes ───────────────────────────────────────────────────
    if not dry_run and matched > 0:
        async with async_session() as db:
            for match in matches:
                result = await db.execute(
                    select(HotelDetails).where(HotelDetails.place_id == match["place_id"])
                )
                hd = result.scalar_one_or_none()
                if hd:
                    platforms = hd.booking_platforms or []
                    expedia_id = match["expedia_id"]
                    if expedia_id not in platforms:
                        platforms.append(expedia_id)
                        hd.booking_platforms = platforms
            await db.commit()

    # ── Print results ────────────────────────────────────────────────────
    logger.info("")
    logger.info("─" * 60)
    logger.info(f"RESULTS for {city}:")
    logger.info(f"  Total hotels:    {len(hotels)}")
    logger.info(f"  Matched:         {matched}")
    logger.info(f"  Failed (no match): {failed}")
    logger.info(f"  Skipped (already have ID): {skipped}")
    logger.info("")

    if matches:
        logger.info("Matches:")
        for m in matches:
            logger.info(f"  ✓ {m['db_name']}")
            logger.info(f"    → {m['expedia_name']} ({m['expedia_id']})")

    return {
        "city": city,
        "total_hotels": len(hotels),
        "matched": matched,
        "failed": failed,
        "skipped": skipped,
    }


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Enrich hotel database with Expedia property IDs"
    )
    parser.add_argument(
        "--city", "-c",
        default=None,
        help="City to enrich (e.g. 'Cairo'). If omitted, enriches all cities found in the DB.",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Run without writing to the database",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Re-match hotels that already have an Expedia ID",
    )
    args = parser.parse_args()

    if args.city:
        cities = [args.city]
    else:
        # Discover all cities with hotels in the database
        from app.core.database import AsyncSessionFactory
        from app.models.place import Place
        from app.models.enums import PlaceCategory
        from sqlalchemy import select, func

        async with AsyncSessionFactory() as db:
            result = await db.execute(
                select(Place.city)
                .where(Place.category == PlaceCategory.hotel)
                .group_by(Place.city)
                .order_by(Place.city)
            )
            cities = [row[0] for row in result.all() if row[0]]

    if not cities:
        logger.info("No cities with hotels found in the database.")
        return

    logger.info(f"Enriching {len(cities)} city(ies): {', '.join(cities)}")
    logger.info("")

    total = {"matched": 0, "failed": 0, "skipped": 0}
    for city in cities:
        result = await enrich_city(city, dry_run=args.dry_run, force=args.force)
        for key in ("matched", "failed", "skipped"):
            total[key] += result.get(key, 0)

    logger.info("=" * 60)
    logger.info("OVERALL SUMMARY")
    logger.info(f"  Total matched:   {total['matched']}")
    logger.info(f"  Total failed:    {total['failed']}")
    logger.info(f"  Total skipped:   {total['skipped']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
