"""Populate dubai_places_class_diagram.json description field from raw data files."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "..", "data", "raw_data")
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

RAW_FILES = [
    os.path.join(RAW_DIR, "dubai_hotel.json"),
    os.path.join(RAW_DIR, "dubai_restaurant.json"),
    os.path.join(RAW_DIR, "dubai_attractions.json"),
]

# Load class diagram data
with open(CD_PATH, "r", encoding="utf-8") as f:
    cd_data = json.load(f)

print(f"Class diagram places: {len(cd_data)}")

# Count empty descriptions before
empty_before = sum(1 for p in cd_data if not p.get("description") or p["description"].strip() == "")
print(f"Empty descriptions before: {empty_before}/{len(cd_data)}")

# Build description lookup from all raw files
# Priority: hotel -> restaurant -> attraction (last writer wins if overlap)
desc_lookup = {}
raw_stats = {"total_descriptions": 0, "usable_descriptions": 0, "sources": {}}

for raw_path in RAW_FILES:
    if not os.path.exists(raw_path):
        print(f"  WARNING: {raw_path} not found, skipping")
        continue

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    source_name = os.path.basename(raw_path)
    count_with_desc = 0

    for entry in raw_data:
        hid = entry.get("id", "")
        raw_desc = entry.get("description", "")
        raw_stats["total_descriptions"] += 1

        if not hid:
            continue

        # Skip empty, N/A, or very short descriptions
        if not raw_desc or raw_desc.strip() in ("", "N/A", "n/a", "None", "null"):
            continue

        desc = raw_desc.strip()
        if len(desc) < 5:
            continue

        count_with_desc += 1
        raw_stats["usable_descriptions"] += 1

        # Only set if not already set (first source wins)
        if hid not in desc_lookup:
            desc_lookup[hid] = desc
            raw_stats["sources"][source_name] = raw_stats["sources"].get(source_name, 0) + 1

    print(f"  {source_name}: {len(raw_data)} entries, {count_with_desc} with usable descriptions")

print(f"\nTotal usable descriptions from raw data: {raw_stats['usable_descriptions']}")
print(f"Unique place IDs with descriptions: {len(desc_lookup)}")
print(f"Sources: {raw_stats['sources']}")

# Match and populate
matched = 0
updated = 0
already_had = 0

for place in cd_data:
    pid = place.get("placeId", "")
    if pid in desc_lookup:
        matched += 1
        current_desc = place.get("description", "").strip()
        if current_desc and current_desc not in ("", "N/A", "None"):
            already_had += 1
        else:
            place["description"] = desc_lookup[pid]
            updated += 1

# Count empty descriptions after
empty_after = sum(1 for p in cd_data if not p.get("description") or p["description"].strip() == "")

print(f"\n=== Results ===")
print(f"Matched (placeId found in raw): {matched}")
print(f"Already had description: {already_had}")
print(f"Updated descriptions: {updated}")
print(f"Empty descriptions after: {empty_after}/{len(cd_data)}")
print(f"Improvement: {empty_before} -> {empty_after} ({empty_before - empty_after} filled)")

# Show sample of updated descriptions
print(f"\nSample updated descriptions:")
updated_count = 0
for place in cd_data:
    pid = place.get("placeId", "")
    if pid in desc_lookup and updated_count < 3:
        current = place.get("description", "")
        if current and len(current) > 10:
            print(f"  {place['name']} ({place['category']}):")
            print(f"    {current[:150]}...")
            updated_count += 1

# Save
with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(cd_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved updated {CD_PATH}")
