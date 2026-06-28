"""Check if hostels exist in the Cairo database."""
import asyncio
import json
import sys
import os

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session
from app.repositories.place_repo import PlaceRepository


async def check():
    async with async_session() as session:
        repo = PlaceRepository(session)
        places = await repo.get_places_by_city_diverse('Cairo', per_accommodation=10)
        hotels = [p for p in places if p.get('category') == 'hotel']
        
        types = {}
        for h in hotels:
            t = h.get('accommodation_type', '?')
            types[t] = types.get(t, 0) + 1
        
        print(f"Total hotels: {len(hotels)}")
        print("Types:", json.dumps(types, indent=2))
        print()
        
        sorted_hotels = sorted(hotels, key=lambda h: -(h.get('popularity_score', 0) or 0))
        for h in sorted_hotels:
            print(f"  - {h['name']} ({h.get('accommodation_type', '?')}) rating={h.get('rating', '?')} score={h.get('popularity_score', '?')}")


asyncio.run(check())
