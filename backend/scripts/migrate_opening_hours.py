"""Migrate openingHours to top-level Place field and set hotels to 24/7.

Changes per updated class diagram:
- Place now has openingHours: Map<DayOfWeek, String> directly
- RestaurantDetails no longer has openingHours
- AttractionDetails no longer has openingHours
- Hotels should have openingHours set to "24/7" (open 24 hours)
"""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "Cairo": os.path.join(PROJECT_ROOT, "..", "data", "cairo", "cairo_places_class_diagram.json"),
    "Dubai": os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json"),
}

HOURS_24_7 = {
    "monday": "24/7",
    "tuesday": "24/7",
    "wednesday": "24/7",
    "thursday": "24/7",
    "friday": "24/7",
    "saturday": "24/7",
    "sunday": "24/7",
}

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def migrate_place(place):
    """Migrate openingHours for a single place. Returns (hours_migrated, hotels_set, removed_from_rest, removed_from_attr)."""
    hours_migrated = 0
    hotels_set = 0
    removed_rest = 0
    removed_attr = 0

    cat = place.get("category", "")

    # --- Restaurants: move openingHours from restaurantDetails to top-level ---
    if cat == "RESTAURANT" and place.get("restaurantDetails"):
        rd = place["restaurantDetails"]
        if rd.get("openingHours") and isinstance(rd["openingHours"], dict) and len(rd["openingHours"]) > 0:
            # Only set top-level if not already set
            if not place.get("openingHours"):
                place["openingHours"] = rd["openingHours"]
                hours_migrated += 1
            # Remove from sub-detail
            del rd["openingHours"]
            removed_rest += 1

    # --- Attractions: move openingHours from attractionDetails to top-level ---
    if cat == "ATTRACTION" and place.get("attractionDetails"):
        ad = place["attractionDetails"]
        if ad.get("openingHours") and isinstance(ad["openingHours"], dict) and len(ad["openingHours"]) > 0:
            if not place.get("openingHours"):
                place["openingHours"] = ad["openingHours"]
                hours_migrated += 1
            del ad["openingHours"]
            removed_attr += 1

    # --- Hotels: set openingHours to 24/7 ---
    if cat == "HOTEL":
        if not place.get("openingHours"):
            place["openingHours"] = dict(HOURS_24_7)
            hotels_set += 1

    return hours_migrated, hotels_set, removed_rest, removed_attr


for name, path in FILES.items():
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print(f"  {name.upper()} MIGRATION")
    print(f"{'='*60}")
    print(f"Total places: {len(data)}")

    total_migrated = 0
    total_hotels_set = 0
    total_removed_rest = 0
    total_removed_attr = 0

    for place in data:
        h, hotel, rr, ra = migrate_place(place)
        total_migrated += h
        total_hotels_set += hotel
        total_removed_rest += rr
        total_removed_attr += ra

    print(f"  Hours migrated (sub-detail -> top-level): {total_migrated}")
    print(f"  Hotels set to 24/7: {total_hotels_set}")
    print(f"  Removed from restaurantDetails: {total_removed_rest}")
    print(f"  Removed from attractionDetails: {total_removed_attr}")

    # Verify
    with_top_level = sum(1 for p in data if p.get("openingHours"))
    rest_with_oh = sum(1 for p in data if p.get("category") == "RESTAURANT" and p.get("restaurantDetails") and p["restaurantDetails"].get("openingHours"))
    attr_with_oh = sum(1 for p in data if p.get("category") == "ATTRACTION" and p.get("attractionDetails") and p["attractionDetails"].get("openingHours"))
    hotels = sum(1 for p in data if p.get("category") == "HOTEL")
    hotels_with_247 = sum(1 for p in data if p.get("category") == "HOTEL" and p.get("openingHours") and p["openingHours"].get("monday") == "24/7")

    print(f"\n  === Verification ===")
    print(f"  Places with top-level openingHours: {with_top_level}/{len(data)}")
    print(f"  Restaurants still with openingHours in sub-detail: {rest_with_oh}")
    print(f"  Attractions still with openingHours in sub-detail: {attr_with_oh}")
    print(f"  Hotels with 24/7 hours: {hotels_with_247}/{hotels}")

    # Show sample
    print(f"\n  Sample top-level openingHours:")
    for p in data[:3]:
        oh = p.get("openingHours", {})
        if oh:
            print(f"    {p['name']} ({p['category']}): {oh}")

    # Save
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: {path}")
