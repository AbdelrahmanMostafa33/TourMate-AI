"""Extract Cairo subcategory-to-tags mapping and Dubai attraction subcategories."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAIRO_PATH = os.path.join(PROJECT_ROOT, "..", "data", "cairo", "cairo_places_class_diagram.json")
DUBAI_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

# Load Cairo data
with open(CAIRO_PATH, "r", encoding="utf-8") as f:
    cairo_data = json.load(f)

# Extract Cairo subcategory -> tags mapping
cairo_attrs = [p for p in cairo_data if p.get("category") == "ATTRACTION" and p.get("attractionDetails")]
subcat_tags = {}
for p in cairo_attrs:
    subcat = p["attractionDetails"].get("subcategory", "N/A")
    tags = p["attractionDetails"].get("tags", [])
    if subcat not in subcat_tags:
        subcat_tags[subcat] = set()
    subcat_tags[subcat].update(tags)

print("=== Cairo Subcategory -> Tags Mapping ===")
for subcat in sorted(subcat_tags.keys()):
    print(f"  {subcat}: {sorted(subcat_tags[subcat])}")

# Load Dubai data
with open(DUBAI_PATH, "r", encoding="utf-8") as f:
    dubai_data = json.load(f)

# Extract Dubai attraction subcategories
dubai_attrs = [p for p in dubai_data if p.get("category") == "ATTRACTION" and p.get("attractionDetails")]
dubai_subcats = {}
for p in dubai_attrs:
    subcat = p["attractionDetails"].get("subcategory", "N/A")
    dubai_subcats[subcat] = dubai_subcats.get(subcat, 0) + 1

print("\n=== Dubai Attraction Subcategories ===")
for subcat, count in sorted(dubai_subcats.items(), key=lambda x: -x[1]):
    print(f"  {subcat}: {count}")

# Check overlap
cairo_subcats = set(subcat_tags.keys())
dubai_subcats_set = set(dubai_subcats.keys())
overlap = cairo_subcats & dubai_subcats_set
only_cairo = cairo_subcats - dubai_subcats_set
only_dubai = dubai_subcats_set - cairo_subcats

print(f"\n=== Subcategory Overlap ===")
print(f"  Overlapping: {sorted(overlap)}")
print(f"  Only in Cairo: {sorted(only_cairo)}")
print(f"  Only in Dubai: {sorted(only_dubai)}")
