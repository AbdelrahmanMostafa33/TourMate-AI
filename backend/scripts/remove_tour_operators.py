"""Remove tour operator entries from generic 'Tourist attraction' type.

Keeps non-tour generic attractions (landmarks, spots, etc.) but removes
entries whose names indicate they are tour agencies, safari operators,
travel packages, etc.
"""
import json
import os

DUBAI_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dubai", "dubai_places_class_diagram.json")

# Keywords that indicate a tour operator / travel agency in attraction names
TOUR_OPERATOR_KEYWORDS = [
    "tour", "safari", "travel", "trekking", "package",
    "guide", "trip", "excursion",
]


def is_tour_operator(name):
    """Check if an attraction name indicates a tour operator."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in TOUR_OPERATOR_KEYWORDS)


def main():
    with open(DUBAI_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Starting count: {len(data)} items")

    kept = []
    removed = []

    for item in data:
        if item.get("category") == "ATTRACTION":
            at = item.get("attractionDetails", {}).get("attractionType", "")
            subcat = item.get("attractionDetails", {}).get("subCategory", "")
            # Only target generic "Tourist attraction" type with "attraction" subcategory
            if at.lower() == "tourist attraction" and subcat.lower() == "attraction":
                if is_tour_operator(item.get("name", "")):
                    removed.append(item)
                    continue
        kept.append(item)

    print(f"Removed: {len(removed)} tour operator entries")
    print(f"Remaining: {len(kept)} items")

    # Show removed names
    print(f"\nRemoved entries:")
    for item in removed:
        print(f"  - {item.get('name', '')}")

    # Category breakdown
    cats = {}
    for item in kept:
        c = item.get("category", "UNKNOWN")
        cats[c] = cats.get(c, 0) + 1
    print("\nCategory breakdown after removal:")
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")

    with open(DUBAI_PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)

    print(f"\nSaved cleaned file: {DUBAI_PATH}")


if __name__ == "__main__":
    main()
