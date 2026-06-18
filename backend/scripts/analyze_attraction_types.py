"""Analyze and classify Dubai attraction types to identify non-real tourist attractions."""
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
    "meat products store", "light bulb supplier",
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
]

# Keywords that DO indicate a real tourist attraction
REAL_ATTRACTION_KEYWORDS = [
    "tourist attraction", "park", "shopping mall", "mosque", "movie theater",
    "historical landmark", "museum", "market", "traditional market", "disco club",
    "night club", "bar", "lounge bar", "pub", "sports bar", "hookah bar",
    "cocktail bar", "beach club", "amusement park", "theme park", "water park",
    "beach", "public beach", "heritage museum", "indoor playground", "playground",
    "garden", "performing arts theater", "observation deck", "bridge", "island",
    "children's amusement center", "live music venue", "adventure sports center",
    "laser tag center", "miniature golf course", "landmark", "children's museum",
    "art museum", "history museum", "aquarium", "night market", "haunted house",
    "monument", "cultural landmark", "ice skating rink", "visitor center",
    "beer garden", "art gallery", "hiking area", "racecourse", "recreation center",
    "ski resort", "campground", "fortress", "ferris wheel", "promenade",
    "marina", "scenic spot", "heritage preservation", "community garden",
    "heritage place museum", "historical place museum", "archaeological museum",
    "outdoor swimming pool", "swimming pool", "swimming facility", "swim club",
    "dog park", "city park", "leisure center", "children's club",
    "sports complex", "sports club", "pool hall", "pool billard club",
    "bowling club", "tennis club", "basketball court", "athletic track",
    "yacht club", "boat club", "fishing club", "social club", "dance club",
    "karaoke bar", "comedy club", "dinner theater", "tapas bar", "tiki bar",
    "wine bar", "gastropub", "irish pub", "chop bar", "beer garden",
    "observation deck", "fountain", "opera house", "auditorium",
    "exhibition and trade center", "performing arts theater",
    "computer club", "chess club", "boxing club", "jujitsu school",
    "ballet school", "dance school", "art school",
]


def classify_type(attraction_type):
    """Classify an attraction type as real or non-real."""
    at_lower = attraction_type.lower().strip()
    if not at_lower:
        return "empty"
    # Check non-attraction keywords first
    for kw in NON_ATTRACTION_KEYWORDS:
        if kw in at_lower:
            return "non-attraction"
    # Check real attraction keywords
    for kw in REAL_ATTRACTION_KEYWORDS:
        if kw in at_lower:
            return "real-attraction"
    return "uncategorized"


def main():
    with open(DUBAI_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    attractions = [i for i in data if i.get("category") == "ATTRACTION"]
    print(f"Total attractions: {len(attractions)}\n")

    # Classify each attraction
    results = {"real-attraction": [], "non-attraction": [], "uncategorized": [], "empty": []}
    type_classification = {}

    for item in attractions:
        at = item.get("attractionDetails", {}).get("attractionType", "")
        cls = classify_type(at)
        results[cls].append(item)
        type_classification[at] = cls

    # Print summary
    print("=== CLASSIFICATION SUMMARY ===")
    for cls, items in results.items():
        print(f"  {cls}: {len(items)}")

    # Print non-attraction types
    print(f"\n=== NON-ATTRACTION TYPES ({len(results['non-attraction'])} items) ===")
    non_attraction_types = {}
    for item in results["non-attraction"]:
        at = item["attractionDetails"].get("attractionType", "")
        non_attraction_types[at] = non_attraction_types.get(at, 0) + 1
    for t, c in sorted(non_attraction_types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    # Print uncategorized types
    if results["uncategorized"]:
        print(f"\n=== UNCATEGORIZED TYPES ({len(results['uncategorized'])} items) ===")
        uncategorized_types = {}
        for item in results["uncategorized"]:
            at = item["attractionDetails"].get("attractionType", "")
            uncategorized_types[at] = uncategorized_types.get(at, 0) + 1
        for t, c in sorted(uncategorized_types.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

    # Print real attraction types (top 20)
    print(f"\n=== REAL ATTRACTION TYPES (top 20 of {len(results['real-attraction'])} items) ===")
    real_types = {}
    for item in results["real-attraction"]:
        at = item["attractionDetails"].get("attractionType", "")
        real_types[at] = real_types.get(at, 0) + 1
    for t, c in sorted(real_types.items(), key=lambda x: -x[1])[:20]:
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
