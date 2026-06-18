"""Populate dubai_places_class_diagram.json attraction tags using Cairo's subcategory-to-tags mapping."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAIRO_PATH = os.path.join(PROJECT_ROOT, "..", "data", "cairo", "cairo_places_class_diagram.json")
DUBAI_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

# --- Step 1: Build subcategory -> tags mapping from Cairo ---
with open(CAIRO_PATH, "r", encoding="utf-8") as f:
    cairo_data = json.load(f)

cairo_attrs = [p for p in cairo_data if p.get("category") == "ATTRACTION" and p.get("attractionDetails")]
subcat_tags = {}
for p in cairo_attrs:
    subcat = p["attractionDetails"].get("subcategory", "N/A")
    tags = p["attractionDetails"].get("tags", [])
    if subcat not in subcat_tags:
        subcat_tags[subcat] = set()
    subcat_tags[subcat].update(tags)

# Convert sets to sorted lists for clean output
subcat_tags = {k: sorted(v) for k, v in subcat_tags.items()}

print("=== Cairo Subcategory -> Tags Mapping ===")
for subcat in sorted(subcat_tags.keys()):
    print(f"  {subcat}: {subcat_tags[subcat]}")

# --- Step 2: Apply mapping to Dubai attractions ---
with open(DUBAI_PATH, "r", encoding="utf-8") as f:
    dubai_data = json.load(f)

dubai_attrs = [p for p in dubai_data if p.get("category") == "ATTRACTION" and p.get("attractionDetails")]
print(f"\nTotal Dubai attractions with attractionDetails: {len(dubai_attrs)}")

updated = 0
skipped = 0
no_mapping = 0

for place in dubai_data:
    if place.get("category") != "ATTRACTION":
        continue
    if place.get("attractionDetails") is None:
        continue

    subcat = place["attractionDetails"].get("subcategory", "N/A")
    current_tags = place["attractionDetails"].get("tags", [])

    # Skip if already has tags
    if current_tags:
        skipped += 1
        continue

    # Look up mapping
    if subcat in subcat_tags:
        place["attractionDetails"]["tags"] = subcat_tags[subcat]
        updated += 1
    else:
        no_mapping += 1
        print(f"  WARNING: No mapping for subcategory '{subcat}' in {place['name']}")

# Count tags after
total_with_tags = sum(
    1 for p in dubai_data
    if p.get("category") == "ATTRACTION"
    and p.get("attractionDetails") is not None
    and p["attractionDetails"].get("tags")
)
total_attrs = sum(
    1 for p in dubai_data
    if p.get("category") == "ATTRACTION"
    and p.get("attractionDetails") is not None
)

print(f"\n=== Results ===")
print(f"Updated (tags populated): {updated}")
print(f"Skipped (already had tags): {skipped}")
print(f"No mapping found: {no_mapping}")
print(f"Attractions with tags after: {total_with_tags}/{total_attrs}")

# Show tag frequency in Dubai after
print(f"\n=== Dubai Tag Frequency (after) ===")
freq = {}
for p in dubai_data:
    if p.get("category") == "ATTRACTION" and p.get("attractionDetails"):
        for t in p["attractionDetails"].get("tags", []):
            freq[t] = freq.get(t, 0) + 1
for t, c in sorted(freq.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

# Show sample
print(f"\n=== Sample Updated Entries ===")
count = 0
for p in dubai_data:
    if p.get("category") == "ATTRACTION" and p.get("attractionDetails"):
        tags = p["attractionDetails"].get("tags", [])
        if tags and count < 5:
            print(f"  {p['name']} ({p['attractionDetails'].get('subcategory')}): {tags}")
            count += 1

# Save
with open(DUBAI_PATH, "w", encoding="utf-8") as f:
    json.dump(dubai_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved updated {DUBAI_PATH}")
