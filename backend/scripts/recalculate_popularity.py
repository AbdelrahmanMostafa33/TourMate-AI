"""Recalculate popularityScore using Bayesian formula per city per category.

Formula:
Score = 100 * [0.6 * (WR/5) + 0.4 * (ln(1+v) / ln(1+v_max))]

Where:
  WR = (v/(v+m))*R + (m/(v+m))*C
  R  = average rating of the place
  v  = number of reviews
  C  = global average rating within the category
  m  = 50 (minimum review threshold)
  v_max = max review count within the category
"""

import json
import math
import os
import sys

# Fix Windows console encoding for Unicode characters (RTL marks, etc.)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "Cairo": os.path.join(PROJECT_ROOT, "..", "data", "cairo", "cairo_places_class_diagram.json"),
    "Dubai": os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json"),
}

M = 50  # Minimum review threshold


def calculate_score(rating, review_count, global_avg_rating, v_max):
    """Calculate Bayesian popularity score (0-100)."""
    R = rating
    v = review_count
    C = global_avg_rating
    m = M

    # Step 1: Bayesian Quality Score
    WR = (v / (v + m)) * R + (m / (v + m)) * C

    # Step 2: Normalize Quality
    Q = WR / 5.0

    # Step 3: Popularity Score (logarithmic)
    if v_max > 0:
        VOL = math.log(1 + v) / math.log(1 + v_max)
    else:
        VOL = 0

    # Final Score
    score = 100 * (0.6 * Q + 0.4 * VOL)

    return round(score, 1)


for city_name, path in FILES.items():
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print(f"  {city_name.upper()} — POPULARITY RECALCULATION")
    print(f"{'='*60}")
    print(f"Total places: {len(data)}")

    # Group by category
    categories = {}
    for p in data:
        cat = p.get("category", "UNKNOWN")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    for cat, places in sorted(categories.items()):
        print(f"\n--- {cat} ({len(places)} places) ---")

        # Calculate category-level stats
        ratings = [p.get("rating", 0) for p in places if p.get("rating")]
        review_counts = [p.get("reviewCount", 0) for p in places]

        if not ratings:
            print("  No ratings found, skipping")
            continue

        global_avg = sum(ratings) / len(ratings)
        v_max = max(review_counts) if review_counts else 0

        print(f"  Global avg rating (C): {global_avg:.2f}")
        print(f"  Max reviews (v_max): {v_max}")

        # Show distribution of current scores
        old_scores = [p.get("popularityScore", 0) for p in places]

        # Recalculate
        new_scores = []
        for p in places:
            rating = p.get("rating", 0)
            review_count = p.get("reviewCount", 0)
            old_score = p.get("popularityScore", 0)

            new_score = calculate_score(rating, review_count, global_avg, v_max)
            new_scores.append(new_score)

            # Update in place
            p["popularityScore"] = new_score

        # Stats
        avg_old = sum(old_scores) / len(old_scores)
        avg_new = sum(new_scores) / len(new_scores)
        min_new = min(new_scores)
        max_new = max(new_scores)

        print(f"  Old avg score: {avg_old:.1f}")
        print(f"  New avg score: {avg_new:.1f}")
        print(f"  Score range: {min_new:.1f} - {max_new:.1f}")

        # Show top 5 and bottom 5
        sorted_places = sorted(places, key=lambda p: p["popularityScore"], reverse=True)
        print(f"\n  Top 5:")
        for p in sorted_places[:5]:
            print(f"    {p['name']}: {p['popularityScore']} (rating: {p.get('rating')}, reviews: {p.get('reviewCount')})")
        print(f"\n  Bottom 5:")
        for p in sorted_places[-5:]:
            print(f"    {p['name']}: {p['popularityScore']} (rating: {p.get('rating')}, reviews: {p.get('reviewCount')})")

    # Save
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: {path}")
