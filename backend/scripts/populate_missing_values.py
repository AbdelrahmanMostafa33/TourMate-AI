"""Populate missing rating and reviewCount in dubai_places_class_diagram.json.

Matches attractions by placeId and fills in missing values from raw dubai_attractions.json.
"""
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai_attractions.json")
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

# Load raw data
with open(RAW_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Build lookup by placeId
raw_lookup = {}
for item in raw_data:
    pid = item.get("id", "")
    if pid:
        raw_lookup[pid] = item

print(f"Raw attractions loaded: {len(raw_data)}")
print(f"Raw lookup entries: {len(raw_lookup)}")

# Load class diagram data
with open(CD_PATH, "r", encoding="utf-8") as f:
    cd_data = json.load(f)

print(f"Class diagram items: {len(cd_data)}")

# Populate missing values
rating_filled = 0
review_filled = 0
not_found = 0

for item in cd_data:
    if item.get("category") != "ATTRACTION":
        continue

    pid = item.get("placeId", "")
    if pid not in raw_lookup:
        not_found += 1
        continue

    raw = raw_lookup[pid]

    # Fill missing rating
    current_rating = item.get("rating") or 0
    raw_rating = raw.get("rating") or 0
    if current_rating == 0 and raw_rating > 0:
        item["rating"] = raw_rating
        rating_filled += 1

    # Fill missing reviewCount
    current_reviews = item.get("reviewCount") or 0
    if current_reviews == 0:
        # Try to extract from reviews_json (can be string or list)
        reviews_json = raw.get("reviews_json", "")
        reviews = None
        if isinstance(reviews_json, list):
            reviews = reviews_json
        elif isinstance(reviews_json, str) and reviews_json.strip() and reviews_json.strip() not in ["[]", "null"]:
            try:
                reviews = json.loads(reviews_json)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(reviews, list) and len(reviews) > 0:
            item["reviewCount"] = len(reviews)
            review_filled += 1

print(f"\n=== Results ===")
print(f"Rating filled: {rating_filled}")
print(f"Review count filled: {review_filled}")
print(f"Not found in raw: {not_found}")

# Verify after
missing_rating = sum(1 for i in cd_data if i.get("category") == "ATTRACTION" and (not i.get("rating") or i["rating"] == 0))
missing_reviews = sum(1 for i in cd_data if i.get("category") == "ATTRACTION" and (not i.get("reviewCount") or i["reviewCount"] == 0))
print(f"\nAfter population:")
print(f"  Missing rating: {missing_rating}")
print(f"  Missing reviewCount: {missing_reviews}")

# Save
with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(cd_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved updated file: {CD_PATH}")
