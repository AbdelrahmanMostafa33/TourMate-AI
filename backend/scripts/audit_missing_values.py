"""Audit missing values in both Cairo and Dubai class diagram data."""

import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "Cairo": os.path.join(PROJECT_ROOT, "..", "data", "cairo", "cairo_places_class_diagram.json"),
    "Dubai": os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json"),
}

CAIRO_REVIEWS = os.path.join(PROJECT_ROOT, "..", "data", "cairo", "cairo_reviews.json")


def is_empty(val):
    """Check if a value is considered empty/null."""
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    if isinstance(val, list) and len(val) == 0:
        return True
    if isinstance(val, dict) and len(val) == 0:
        return True
    return False


def audit_field(data, field, category_filter=None):
    """Audit a single field across all entries or filtered by category."""
    if category_filter:
        subset = [p for p in data if p.get("category") == category_filter]
    else:
        subset = data

    if not subset:
        return None

    total = len(subset)
    missing = sum(1 for p in subset if is_empty(p.get(field)))
    filled = total - missing
    return {"total": total, "filled": filled, "missing": missing, "pct": filled / total * 100}


def audit_subdetail(data, detail_key, detail_fields, category):
    """Audit fields within a sub-detail object."""
    places = [p for p in data if p.get("category") == category and p.get(detail_key) is not None]
    if not places:
        return None

    results = {}
    total = len(places)
    for field in detail_fields:
        missing = sum(1 for p in places if is_empty(p[detail_key].get(field)))
        results[field] = {"total": total, "filled": total - missing, "missing": missing, "pct": (total - missing) / total * 100}
    return results


def print_audit(name, data, reviews_path=None):
    print(f"\n{'='*70}")
    print(f"  {name.upper()} — MISSING VALUES AUDIT")
    print(f"{'='*70}")
    print(f"Total places: {len(data)}")

    # Category counts
    cats = {}
    for p in data:
        c = p.get("category", "N/A")
        cats[c] = cats.get(c, 0) + 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")

    # Core fields
    core_fields = [
        "placeId", "name", "description", "category", "subcategory",
        "rating", "reviewCount", "popularityScore",
        "phone", "website", "mapsLink",
        "lat", "lng", "city", "country", "timezone",
        "photoUrls", "embedding",
    ]

    print(f"\n--- Core Place Fields ---")
    print(f"{'Field':<20} {'Filled':>8} {'Missing':>8} {'%':>6}  Status")
    print(f"{'-'*65}")
    for field in core_fields:
        result = audit_field(data, field)
        if result:
            status = "OK" if result["missing"] == 0 else "WARN" if result["pct"] >= 80 else "MISS"
            print(f"{field:<20} {result['filled']:>8} {result['missing']:>8} {result['pct']:>5.1f}%  {status}")

    # Per-category field audit
    for cat in ["HOTEL", "RESTAURANT", "ATTRACTION"]:
        places = [p for p in data if p.get("category") == cat]
        if not places:
            continue
        print(f"\n--- {cat} Category ({len(places)} places) ---")
        # Check all top-level fields for this category
        all_keys = set()
        for p in places:
            all_keys.update(p.keys())
        for field in sorted(all_keys):
            if field in ["hotelDetails", "restaurantDetails", "attractionDetails"]:
                continue
            result = audit_field(data, field, cat)
            if result and result["missing"] > 0:
                status = "WARN" if result["pct"] >= 80 else "MISS"
                print(f"  {field:<20} {result['filled']:>8}/{result['total']} missing {result['missing']:>6} ({100-result['pct']:.1f}%)  {status}")

    # Sub-details
    print(f"\n--- hotelDetails ---")
    hotel_result = audit_subdetail(data, "hotelDetails", ["placeId", "starClass", "nightlyRate", "amenities", "bookingPlatforms"], "HOTEL")
    if hotel_result:
        print(f"{'Field':<20} {'Filled':>8} {'Missing':>8} {'%':>6}  Status")
        print(f"{'-'*65}")
        for field, r in hotel_result.items():
            status = "OK" if r["missing"] == 0 else "WARN" if r["pct"] >= 80 else "MISS"
            print(f"{field:<20} {r['filled']:>8} {r['missing']:>8} {r['pct']:>5.1f}%  {status}")
    else:
        print("  No hotels found with hotelDetails")

    print(f"\n--- restaurantDetails ---")
    rest_result = audit_subdetail(data, "restaurantDetails", ["cuisineType", "avgCostPerPerson", "openingHours"], "RESTAURANT")
    if rest_result:
        print(f"{'Field':<20} {'Filled':>8} {'Missing':>8} {'%':>6}  Status")
        print(f"{'-'*65}")
        for field, r in rest_result.items():
            status = "OK" if r["missing"] == 0 else "WARN" if r["pct"] >= 80 else "MISS"
            # For openingHours, count sub-fields
            if field == "openingHours":
                restaurants = [p for p in data if p.get("category") == "RESTAURANT" and p.get("restaurantDetails") is not None]
                days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                day_missing = {}
                for d in days:
                    day_missing[d] = sum(1 for p in restaurants if is_empty(p["restaurantDetails"].get("openingHours", {}).get(d)))
                print(f"{field:<20} {r['filled']:>8} {r['missing']:>8} {r['pct']:>5.1f}%  {status}")
                for d in days:
                    dm = day_missing[d]
                    dpct = dm / len(restaurants) * 100 if restaurants else 0
                    ds = "OK" if dm == 0 else "WARN" if dpct >= 80 else "MISS"
                    print(f"  {d:<18} {len(restaurants)-dm:>8} {dm:>8} {100-dpct:>5.1f}%  {ds}")
            else:
                print(f"{field:<20} {r['filled']:>8} {r['missing']:>8} {r['pct']:>5.1f}%  {status}")
    else:
        print("  No restaurants found with restaurantDetails")

    print(f"\n--- attractionDetails ---")
    attr_result = audit_subdetail(data, "attractionDetails", ["subcategory", "tags", "entryFee", "openingHours"], "ATTRACTION")
    if attr_result:
        print(f"{'Field':<20} {'Filled':>8} {'Missing':>8} {'%':>6}  Status")
        print(f"{'-'*65}")
        for field, r in attr_result.items():
            status = "OK" if r["missing"] == 0 else "WARN" if r["pct"] >= 80 else "MISS"
            if field == "openingHours":
                attractions = [p for p in data if p.get("category") == "ATTRACTION" and p.get("attractionDetails") is not None]
                days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                day_missing = {}
                for d in days:
                    day_missing[d] = sum(1 for p in attractions if is_empty(p["attractionDetails"].get("openingHours", {}).get(d)))
                print(f"{field:<20} {r['filled']:>8} {r['missing']:>8} {r['pct']:>5.1f}%  {status}")
                for d in days:
                    dm = day_missing[d]
                    dpct = dm / len(attractions) * 100 if attractions else 0
                    ds = "OK" if dm == 0 else "WARN" if dpct >= 80 else "MISS"
                    print(f"  {d:<18} {len(attractions)-dm:>8} {dm:>8} {100-dpct:>5.1f}%  {ds}")
            else:
                print(f"{field:<20} {r['filled']:>8} {r['missing']:>8} {r['pct']:>5.1f}%  {status}")
    else:
        print("  No attractions found with attractionDetails")

    # Reviews
    if reviews_path and os.path.exists(reviews_path):
        with open(reviews_path, "r", encoding="utf-8") as f:
            reviews = json.load(f)
        place_ids = {p["placeId"] for p in data}
        reviewed = {r.get("placeId") for r in reviews if r.get("placeId")}
        overlap = reviewed & place_ids
        print(f"\n--- Reviews ---")
        print(f"  Total reviews: {len(reviews)}")
        print(f"  Unique places with reviews: {len(reviewed)}")
        print(f"  Places with Place+Review: {len(overlap)}/{len(data)}")
        print(f"  Places missing reviews: {len(data) - len(overlap)}")
    elif name == "Dubai":
        print(f"\n--- Reviews ---")
        print(f"  [MISS] NO REVIEWS FILE EXISTS")
        print(f"  Reviews are embedded in raw dubai_attractions.json but not extracted")


# Run audits
for name, path in FILES.items():
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    reviews_path = CAIRO_REVIEWS if name == "Cairo" else None
    print_audit(name, data, reviews_path)

# Summary comparison
print(f"\n\n{'='*70}")
print(f"  SUMMARY COMPARISON")
print(f"{'='*70}")
print(f"{'Field':<25} {'Cairo':>12} {'Dubai':>12}  Gap")
print(f"{'-'*65}")

compare_fields = [
    ("description", None),
    ("phone", None),
    ("website", None),
    ("photoUrls", None),
    ("embedding", None),
    ("hotelDetails.bookingPlatforms", ("HOTEL", "hotelDetails", "bookingPlatforms")),
    ("hotelDetails.amenities", ("HOTEL", "hotelDetails", "amenities")),
    ("restaurantDetails.openingHours", ("RESTAURANT", "restaurantDetails", "openingHours")),
    ("restaurantDetails.avgCostPerPerson", ("RESTAURANT", "restaurantDetails", "avgCostPerPerson")),
    ("attractionDetails.tags", ("ATTRACTION", "attractionDetails", "tags")),
    ("attractionDetails.openingHours", ("ATTRACTION", "attractionDetails", "openingHours")),
    ("attractionDetails.entryFee", ("ATTRACTION", "attractionDetails", "entryFee")),
]

for label, info in compare_fields:
    c_data = json.load(open(FILES["Cairo"], "r", encoding="utf-8"))
    d_data = json.load(open(FILES["Dubai"], "r", encoding="utf-8"))

    if info is None:
        c_pct = audit_field(c_data, label)["pct"]
        d_pct = audit_field(d_data, label)["pct"]
    else:
        cat, detail, field = info
        c_res = audit_subdetail(c_data, detail, [field], cat)
        d_res = audit_subdetail(d_data, detail, [field], cat)
        c_pct = c_res[field]["pct"] if c_res and field in c_res else 0
        d_pct = d_res[field]["pct"] if d_res and field in d_res else 0

    gap = ""
    if c_pct > d_pct:
        gap = f"Cairo +{c_pct-d_pct:.0f}%"
    elif d_pct > c_pct:
        gap = f"Dubai +{d_pct-c_pct:.0f}%"
    else:
        gap = "Same"

    c_status = "OK" if c_pct >= 100 else "WARN" if c_pct >= 80 else "MISS"
    d_status = "OK" if d_pct >= 100 else "WARN" if d_pct >= 80 else "MISS"

    print(f"{label:<25} {c_pct:>5.1f}% {c_status} {d_pct:>5.1f}% {d_status}  {gap}")
