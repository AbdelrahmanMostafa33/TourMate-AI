"""Populate dubai_places_class_diagram.json restaurant openingHours from raw day fields."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(PROJECT_ROOT, "..", "data", "raw_data", "dubai_restaurant.json")
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

DAY_MAP = {
    "hours_monday": "monday",
    "hours_tuesday": "tuesday",
    "hours_wednesday": "wednesday",
    "hours_thursday": "thursday",
    "hours_friday": "friday",
    "hours_saturday": "saturday",
    "hours_sunday": "sunday",
}

# Load data
with open(RAW_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

with open(CD_PATH, "r", encoding="utf-8") as f:
    cd_data = json.load(f)

print(f"Raw restaurants: {len(raw_data)}")
print(f"Class diagram places: {len(cd_data)}")

# Build lookup by id -> openingHours dict
raw_lookup = {}
usable = 0
for r in raw_data:
    rid = r.get("id", "")
    if not rid:
        continue
    hours = {}
    for raw_key, day_name in DAY_MAP.items():
        val = r.get(raw_key, "")
        if val and str(val).strip():
            hours[day_name] = str(val).strip()
    if hours:
        raw_lookup[rid] = hours
        usable += 1

print(f"Raw restaurants with usable hours: {usable}")

# Match and populate
matched = 0
updated = 0
already_had = 0
no_match = 0

restaurants = [p for p in cd_data if p.get("category") == "RESTAURANT"]
print(f"\nRestaurants in class diagram: {len(restaurants)}")

for place in restaurants:
    pid = place.get("placeId", "")
    if pid in raw_lookup:
        matched += 1
        current = place.get("openingHours")
        if current and isinstance(current, dict) and len(current) > 0:
            already_had += 1
        else:
            place["openingHours"] = raw_lookup[pid]
            updated += 1
    else:
        no_match += 1

# Verify
rest_with_hours = sum(1 for p in cd_data if p.get("category") == "RESTAURANT" and p.get("openingHours"))
total_rest = len(restaurants)

print(f"\n=== Results ===")
print(f"Matched (placeId found in raw): {matched}")
print(f"Already had openingHours: {already_had}")
print(f"Updated: {updated}")
print(f"No match in raw: {no_match}")
print(f"Restaurants with openingHours after: {rest_with_hours}/{total_rest}")

# Sample
print(f"\nSample updated entries:")
count = 0
for p in cd_data:
    if p.get("category") == "RESTAURANT" and p.get("openingHours") and count < 3:
        oh = p["openingHours"]
        print(f"  {p['name']}: {oh}")
        count += 1

# Save
with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(cd_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved: {CD_PATH}")
