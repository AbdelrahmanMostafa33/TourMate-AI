"""Remove attractions with missing ratings or review counts.

Removes ATTRACTION entries where rating is 0/None OR reviewCount is 0/None.
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

with open(CD_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Starting count: {len(data)} items")

kept = []
removed_missing_rating = []
removed_missing_reviews = []

for item in data:
    if item.get("category") == "ATTRACTION":
        rating = item.get("rating") or 0
        reviews = item.get("reviewCount") or 0

        if rating == 0:
            removed_missing_rating.append(item)
            continue
        if reviews == 0:
            removed_missing_reviews.append(item)
            continue

    kept.append(item)

total_removed = len(removed_missing_rating) + len(removed_missing_reviews)
print(f"\nRemoved: {total_removed} entries")
print(f"  Missing rating: {len(removed_missing_rating)}")
print(f"  Missing reviewCount: {len(removed_missing_reviews)}")
print(f"\nRemaining: {len(kept)} items")

# Category breakdown
cats = {}
for item in kept:
    c = item.get("category", "UNKNOWN")
    cats[c] = cats.get(c, 0) + 1
print("\nCategory breakdown after removal:")
for c, n in sorted(cats.items()):
    print(f"  {c}: {n}")

# Show removed names
print(f"\nRemoved (missing rating):")
for item in removed_missing_rating:
    print(f"  - {item.get('name', '')} (rating={item.get('rating')}, reviews={item.get('reviewCount')})")

print(f"\nRemoved (missing reviewCount):")
for item in removed_missing_reviews[:10]:
    print(f"  - {item.get('name', '')} (rating={item.get('rating')}, reviews={item.get('reviewCount')})")
if len(removed_missing_reviews) > 10:
    print(f"  ... and {len(removed_missing_reviews) - 10} more")

with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(kept, f, indent=2, ensure_ascii=False)

print(f"\nSaved cleaned file: {CD_PATH}")
