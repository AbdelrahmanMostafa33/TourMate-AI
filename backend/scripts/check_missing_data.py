"""Check for missing ratings and review counts in dubai_places_class_diagram.json."""
import json
import os

DUBAI_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dubai", "dubai_places_class_diagram.json")

with open(DUBAI_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

total = len(data)
missing_rating = sum(1 for i in data if not i.get("rating") or i["rating"] == 0)
missing_reviews = sum(1 for i in data if not i.get("reviewCount") or i["reviewCount"] == 0)
missing_both = sum(
    1 for i in data
    if (not i.get("rating") or i["rating"] == 0)
    and (not i.get("reviewCount") or i["reviewCount"] == 0)
)

print(f"Total items: {total}")
print(f"Missing/zero rating: {missing_rating}")
print(f"Missing/zero reviewCount: {missing_reviews}")
print(f"Missing both: {missing_both}")

for cat in ["ATTRACTION", "RESTAURANT", "HOTEL"]:
    items = [i for i in data if i.get("category") == cat]
    mr = sum(1 for i in items if not i.get("rating") or i["rating"] == 0)
    mrc = sum(1 for i in items if not i.get("reviewCount") or i["reviewCount"] == 0)
    print(f"\n=== {cat} ===")
    print(f"  Total: {len(items)}")
    print(f"  Missing rating: {mr}")
    print(f"  Missing reviewCount: {mrc}")
