"""Test: verify find_place_for_add can find 'wa7wa7' from the database."""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)

# Need to set up Django-style project root import
sys.path.insert(0, "D:\\Github\\TourMate-AI\\backend")


async def main():
    from ai_engine.services.pool_manager import find_place_for_add

    # Simulate the modifier agent flow — pass an empty pool so it
    # MUST fall back to the database query.
    result = await find_place_for_add(
        modification_request="add wa7wa7 restaurant",
        city="Cairo",
        country="Egypt",
        available_places=[],  # Empty pool — forces DB fallback
        preferences=None,
    )

    if result:
        print(f"✅ FOUND in database:")
        print(f"   Name:     {result.get('name')}")
        print(f"   ID:       {result.get('id')}")
        print(f"   Category: {result.get('category')}")
        print(f"   Rating:   {result.get('rating')}")
        print(f"   City:     {result.get('city')}")
    else:
        print("❌ NOT FOUND in database — wa7wa7 may not exist in the places table")


if __name__ == "__main__":
    asyncio.run(main())
