"""Remove non-attraction entries from dubai_places_class_diagram.json.

Uses the same classification logic as analyze_attraction_types.py to identify
and remove entries whose attractionType does not represent a real tourist attraction.
"""
import json
import os

DUBAI_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dubai", "dubai_places_class_diagram.json")

# Keywords that indicate a NON-tourist attraction (businesses, services, infrastructure)
NON_ATTRACTION_KEYWORDS = [
    # Travel/Tour services (not actual destinations)
    "tour operator", "tour agency", "travel agency", "sightseeing tour agency",
    "helicopter tour agency", "balloon ride tour agency", "boat tour agency",
    "cruise agency", "cruise line company",
    # Event/Entertainment services
    "event management company", "event planner", "entertainment agency",
    "event venue", "event ticket seller",
    # Corporate/Business
    "corporate office", "government office", "business center", "business park",
    "coworking space", "employment consultant", "professional association",
    "association / organization", "film production company", "recording studio",
    # Retail/Shopping (not markets or malls as destinations)
    "clothing store", "store", "supermarket", "electronics store", "jewelry store",
    "bag shop", "home cinema installation", "print shop", "fashion accessories store",
    "jewelry store", "fashion designer", "souvenir store", "mattress store",
    "cell phone store", "golf shop", "men's clothing store", "women's clothing store",
    "fabric store", "collectibles store", "gift shop", "toy store", "liquor store",
    "home goods store", "vaporizer store", "spice store", "pharmacy", "book store",
    "department store", "convenience store", "sporting goods store", "watch store",
    "cricket shop", "meat products store", "furniture store", "general store",
    "handbags shop", "beach clothing store", "cosmetics store", "shoe store",
    "chocolate shop", "baby store", "video game store", "gift wrap store",
    "computer store", "sportswear store", "stationery store", "discount store",
    "perfume store", "herbal medicine store", "discount supermarket", "florist",
    "flower delivery", "bicycle store", "electric bicycle store", "health and beauty shop",
    "thrift store", "outlet mall", "hypermarket", "fruit and vegetable store",
    "indian grocery store", "grocery store", "flea market", "cattle market",
    "seafood wholesaler", "spice wholesaler", "pond fish supplier", "wholesaler",
    "light bulb supplier",
    # Beauty/Personal Care
    "beauty salon", "barber shop", "nail salon", "hair salon", "day spa",
    "facial spa", "skin care clinic", "massage therapist",
    # Fitness/Wellness (services, not destinations)
    "gym", "fitness center", "pilates studio",
    # Automotive/Transportation services
    "car rental agency", "boat rental service", "atv rental service",
    "transportation service", "scooter rental service", "water sports equipment rental service",
    # Real Estate/Residential
    "apartment building", "apartment complex", "condominium complex",
    "housing development", "parking lot",
    # Infrastructure
    "bus stop", "bus station", "bus depot", "subway station", "ferry terminal",
    # Medical/Health services
    "medical center", "swimming instructor",
    # Other services
    "computer service", "modeling agency", "day care center", "personal concierge service",
    "social services organization", "caterer", "magician", "entertainer",
    "theater company", "physical fitness program", "video game rental kiosk",
    # Duplicate of RESTAURANT category (not tourist attractions)
    "restaurant", "massage spa", "hotel", "boutique", "bistro",
    "coffee shop", "dessert shop", "fine dining restaurant", "bakery",
]


def classify_type(attraction_type):
    """Classify an attraction type as real or non-real."""
    at_lower = attraction_type.lower().strip()
    if not at_lower:
        return "empty"
    for kw in NON_ATTRACTION_KEYWORDS:
        if kw in at_lower:
            return "non-attraction"
    return "valid"


def main():
    with open(DUBAI_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Starting count: {len(data)} items")

    # Separate non-attractions from the rest
    kept = []
    removed = []
    removed_types = {}

    for item in data:
        if item.get("category") == "ATTRACTION":
            at = item.get("attractionDetails", {}).get("attractionType", "")
            cls = classify_type(at)
            if cls == "non-attraction":
                removed.append(item)
                removed_types[at] = removed_types.get(at, 0) + 1
                continue
        kept.append(item)

    print(f"Removed: {len(removed)} non-attraction entries")
    print(f"Remaining: {len(kept)} entries")

    # Category breakdown
    cats = {}
    for item in kept:
        c = item.get("category", "UNKNOWN")
        cats[c] = cats.get(c, 0) + 1
    print("\nCategory breakdown after removal:")
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")

    # Show removed types
    print(f"\nRemoved types ({len(removed_types)} unique):")
    for t, c in sorted(removed_types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    # Save
    with open(DUBAI_PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)

    print(f"\nSaved cleaned file: {DUBAI_PATH}")


if __name__ == "__main__":
    main()
