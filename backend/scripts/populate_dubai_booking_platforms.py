"""Populate dubai_places_class_diagram.json bookingPlatforms from dubai_hotel.json raw data."""

import json
import os

# Resolve from project root (backend/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(PROJECT_ROOT, "..", "data", "raw_data", "dubai_hotel.json")
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

# Load data
with open(RAW_PATH, "r", encoding="utf-8") as f:
    raw_hotels = json.load(f)

with open(CD_PATH, "r", encoding="utf-8") as f:
    cd_data = json.load(f)

print(f"Raw hotels: {len(raw_hotels)}")
print(f"Class diagram places: {len(cd_data)}")

# Build lookup by id -> booking_platforms
raw_lookup = {}
for h in raw_hotels:
    hid = h.get("id", "")
    platforms = h.get("booking_platforms", [])
    if hid and platforms:
        raw_lookup[hid] = platforms

print(f"Raw hotels with non-empty booking_platforms: {len(raw_lookup)}")

# Also check what booking_platforms values look like
sample_values = set()
for h in raw_hotels:
    bp = h.get("booking_platforms", [])
    if bp:
        sample_values.add(str(bp)[:200])

print(f"\nSample booking_platforms values:")
for v in sorted(sample_values)[:10]:
    print(f"  {v}")

# Check booking_url as well
booking_url_count = sum(1 for h in raw_hotels if h.get("booking_url"))
print(f"\nRaw hotels with booking_url: {booking_url_count}/{len(raw_hotels)}")

# Match and populate
matched = 0
not_found = 0
updated = 0

for place in cd_data:
    if place.get("category") != "HOTEL":
        continue

    pid = place.get("placeId", "")
    if pid in raw_lookup:
        matched += 1
        platforms = raw_lookup[pid]
        if place.get("hotelDetails") is None:
            not_found += 1
            continue

        current = place["hotelDetails"].get("bookingPlatforms", [])
        if not current and platforms:
            place["hotelDetails"]["bookingPlatforms"] = platforms
            updated += 1
    else:
        not_found += 1

print(f"\nMatched hotels (placeId found in raw): {matched}")
print(f"Not found in raw: {not_found}")
print(f"Updated bookingPlatforms: {updated}")

# Verify before saving
empty_after = sum(
    1 for p in cd_data
    if p.get("category") == "HOTEL"
    and p.get("hotelDetails") is not None
    and not p["hotelDetails"].get("bookingPlatforms")
)
total_hotels = sum(1 for p in cd_data if p.get("category") == "HOTEL")
print(f"\nHotels with empty bookingPlatforms after update: {empty_after}/{total_hotels}")

# Save
with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(cd_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved updated {CD_PATH}")
