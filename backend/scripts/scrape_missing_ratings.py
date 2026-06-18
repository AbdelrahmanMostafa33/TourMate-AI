"""Prepare batch scraping of zero-rating places from Google Maps."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

with open(CD_PATH, "r", encoding="utf-8") as f:
    cd_data = json.load(f)

# Find zero-rating places with reviews
zero_places = [p for p in cd_data if p.get("rating", 0) == 0 and p.get("reviewCount", 0) > 0]

print(f"Total zero-rating places: {len(zero_places)}")
print()

# Sort by review count (highest first - most important to fix)
zero_places.sort(key=lambda p: p.get("reviewCount", 0), reverse=True)

# Output URLs for batch scraping
for i, p in enumerate(zero_places):
    print(f"{i+1}. {p['name']} ({p['category']}) - reviews: {p.get('reviewCount', 0)}")
    print(f"   URL: {p.get('mapsLink', 'N/A')[:120]}...")

# Also save to a JSON file for the scraping script
output = []
for p in zero_places:
    output.append({
        "placeId": p["placeId"],
        "name": p["name"],
        "category": p["category"],
        "reviewCount": p.get("reviewCount", 0),
        "mapsLink": p.get("mapsLink", ""),
    })

output_path = os.path.join(os.path.dirname(__file__), "zero_rating_places.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nSaved {len(output)} places to {output_path}")
