"""Filter restaurants in dubai_places_class_diagram.json.

Keep only restaurants with rating >= 4.0 AND reviewCount >= 100.
"""
import json
import os

DUBAI_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dubai", "dubai_places_class_diagram.json")

MIN_RATING = 4.0
MIN_REVIEWS = 500


def main():
    with open(DUBAI_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Starting count: {len(data)} items")

    kept = []
    removed = []

    for item in data:
        if item.get("category") == "RESTAURANT":
            rating = item.get("rating", 0) or 0
            reviews = item.get("reviewCount", 0) or 0
            if rating >= MIN_RATING and reviews >= MIN_REVIEWS:
                kept.append(item)
            else:
                removed.append(item)
        else:
            kept.append(item)

    # Stats on removed
    removed_ratings = [i.get("rating", 0) or 0 for i in removed]
    removed_reviews = [i.get("reviewCount", 0) or 0 for i in removed]

    print(f"\nRemoved: {len(removed)} restaurants")
    print(f"  Avg rating of removed: {sum(removed_ratings)/len(removed_ratings):.2f}")
    print(f"  Avg reviews of removed: {sum(removed_reviews)/len(removed_reviews):.0f}")
    print(f"  Removed with rating < 4.0: {sum(1 for r in removed_ratings if r < 4.0)}")
    print(f"  Removed with reviews < 100: {sum(1 for r in removed_reviews if r < 100)}")

    print(f"\nRemaining: {len(kept)} items")

    # Category breakdown
    cats = {}
    for item in kept:
        c = item.get("category", "UNKNOWN")
        cats[c] = cats.get(c, 0) + 1
    print("\nCategory breakdown after filtering:")
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")

    # Stats on kept restaurants
    kept_restaurants = [i for i in kept if i.get("category") == "RESTAURANT"]
    kept_ratings = [i.get("rating", 0) or 0 for i in kept_restaurants]
    kept_reviews = [i.get("reviewCount", 0) or 0 for i in kept_restaurants]
    print(f"\nKept restaurants stats:")
    print(f"  Count: {len(kept_restaurants)}")
    print(f"  Avg rating: {sum(kept_ratings)/len(kept_ratings):.2f}")
    print(f"  Avg reviews: {sum(kept_reviews)/len(kept_reviews):.0f}")
    print(f"  Min rating: {min(kept_ratings)}")
    print(f"  Min reviews: {min(kept_reviews)}")

    with open(DUBAI_PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)

    print(f"\nSaved filtered file: {DUBAI_PATH}")


if __name__ == "__main__":
    main()
