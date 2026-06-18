"""Fix zero ratings in Dubai class diagram by pulling from raw data files."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")
RAW_DIR = os.path.join(PROJECT_ROOT, "..", "data", "raw_data")

RAW_FILES = [
    os.path.join(RAW_DIR, "dubai_hotel.json"),
    os.path.join(RAW_DIR, "dubai_restaurant.json"),
    os.path.join(RAW_DIR, "dubai_attractions.json"),
]

# Load class diagram
with open(CD_PATH, "r", encoding="utf-8") as f:
    cd_data = json.load(f)

# Find zero-rating places with reviews
zero_places = [p for p in cd_data if p.get("rating", 0) == 0 and p.get("reviewCount", 0) > 0]
zero_ids = {p["placeId"] for p in zero_places}
print(f"Zero-rating places with reviews: {len(zero_places)}")

# Build rating lookup from all raw files
rating_lookup = {}
for raw_path in RAW_FILES:
    if not os.path.exists(raw_path):
        continue
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    source = os.path.basename(raw_path)
    found = 0
    for entry in raw_data:
        eid = entry.get("id", "")
        if eid in zero_ids:
            raw_rating = entry.get("rating", 0)
            if raw_rating and raw_rating > 0:
                rating_lookup[eid] = raw_rating
                found += 1
    print(f"  {source}: found {found} ratings for zero-rating places")

print(f"\nTotal ratings recovered: {len(rating_lookup)}/{len(zero_places)}")

# Apply fixes
fixed = 0
for place in cd_data:
    pid = place.get("placeId", "")
    if pid in rating_lookup:
        old = place["rating"]
        place["rating"] = rating_lookup[pid]
        fixed += 1
        if fixed <= 5:
            print(f"  Fixed: {place['name']} rating {old} -> {place['rating']}")

print(f"\nTotal fixed: {fixed}")

# Verify
still_zero = sum(1 for p in cd_data if p.get("rating", 0) == 0 and p.get("reviewCount", 0) > 0)
print(f"Still zero-rating with reviews: {still_zero}")

# Show remaining zero-rating places
if still_zero > 0:
    print(f"\nRemaining zero-rating places:")
    for p in cd_data:
        if p.get("rating", 0) == 0 and p.get("reviewCount", 0) > 0:
            print(f"  {p['name']} ({p['category']}) - reviews: {p.get('reviewCount')}")

# Save
with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(cd_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved: {CD_PATH}")
