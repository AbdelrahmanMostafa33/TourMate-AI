"""Test _swap_accommodation_surgically logic for hostels in Cairo."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_engine.tools.slot_normalizer import map_accommodation_to_type
from ai_engine.tools.places_tool import get_places_for_city


async def check():
    # Test 1: map_accommodation_to_type
    canonical = map_accommodation_to_type(["hostel"])
    print(f"[1] map_accommodation_to_type(['hostel']) = '{canonical}'")
    
    canonical2 = map_accommodation_to_type(["hostels"])
    print(f"[2] map_accommodation_to_type(['hostels']) = '{canonical2}'")

    # Test 3: what get_places_for_city returns
    all_places = await get_places_for_city("Cairo")
    hotels = [p for p in all_places if p.get("category") == "hotel"]
    hostel_types = [p.get("accommodation_type") for p in hotels if p.get("accommodation_type")]
    unique_types = set(str(t) for t in hostel_types)
    print(f"\n[3] Total hotels in Cairo: {len(hotels)}")
    print(f"    Accommodation types found: {unique_types}")
    
    hostels = [p for p in hotels if (p.get("accommodation_type") or "").lower() == "hostel"]
    print(f"    Hostels found: {len(hostels)}")
    for h in hostels:
        acc_type = h.get("accommodation_type", "?")
        print(f"      - {h['name']} (type='{acc_type}', rating={h.get('rating')})")

    # Test 4: Simulate _swap_accommodation_surgically exact filter
    canonical_type = "hostel"
    matching = [
        p for p in all_places
        if p.get("category") == "hotel"
        and (
            canonical_type in (p.get("accommodation_type") or "").lower()
            or (p.get("accommodation_type") or "").lower() in canonical_type
        )
    ]
    print(f"\n[4] Hotels matching filter 'hostel': {len(matching)}")
    for m in matching:
        print(f"      - {m['name']} (type='{m.get('accommodation_type', '?')}')")


asyncio.run(check())
