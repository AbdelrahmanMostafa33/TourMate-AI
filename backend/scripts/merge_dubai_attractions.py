"""
Merge dubai_attractions.json (raw_data) into dubai_places_class_diagram.json.

Converts attraction data from the raw schema to the class diagram schema
and appends to the existing dataset.
"""
import json
import os

SOURCE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw_data", "dubai_attractions.json")
TARGET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dubai", "dubai_places_class_diagram.json")


def parse_photo_urls(photo_urls_field):
    """Convert photo_urls to a list of URLs."""
    if not photo_urls_field:
        return []
    if isinstance(photo_urls_field, list):
        return [u for u in photo_urls_field if u]
    if isinstance(photo_urls_field, str):
        urls = [u.strip() for u in photo_urls_field.split(",") if u.strip()]
        return urls
    return []


def extract_amenities(about_attributes_json, has_food_and_drinks, has_parking, has_food_court):
    """Extract amenity list from about_attributes_json and boolean flags."""
    amenities = []
    if has_food_and_drinks == "True" or has_food_and_drinks is True:
        amenities.append("Food and drinks")
    if has_parking == "True" or has_parking is True:
        amenities.append("Parking")
    if has_food_court == "True" or has_food_court is True:
        amenities.append("Food court")

    if isinstance(about_attributes_json, dict):
        for category_name, attrs in about_attributes_json.items():
            if isinstance(attrs, list):
                for attr in attrs:
                    if isinstance(attr, dict) and attr.get("available"):
                        amenities.append(attr.get("name", ""))

    return [a for a in amenities if a]


def convert_attraction(item):
    """Convert a raw attraction item to the class diagram schema."""
    # Build openingHours from individual day fields
    day_map = {
        "monday": item.get("hours_monday", ""),
        "tuesday": item.get("hours_tuesday", ""),
        "wednesday": item.get("hours_wednesday", ""),
        "thursday": item.get("hours_thursday", ""),
        "friday": item.get("hours_friday", ""),
        "saturday": item.get("hours_saturday", ""),
        "sunday": item.get("hours_sunday", ""),
    }
    opening_hours = {k: v for k, v in day_map.items() if v}

    # Parse about_attributes_json if it's a string
    about_attrs = item.get("about_attributes_json", {})
    if isinstance(about_attrs, str):
        try:
            about_attrs = json.loads(about_attrs)
        except (json.JSONDecodeError, TypeError):
            about_attrs = {}

    amenities = extract_amenities(
        about_attrs,
        item.get("has_food_and_drinks", ""),
        item.get("has_parking", ""),
        item.get("has_food_court", ""),
    )

    # Parse popular_times_json for popularity score
    popular_times = item.get("popular_times_json", {})
    if isinstance(popular_times, str):
        try:
            popular_times = json.loads(popular_times)
        except (json.JSONDecodeError, TypeError):
            popular_times = {}

    # Calculate a basic popularity score from popular times
    popularity_score = 60.0  # default
    if isinstance(popular_times, dict) and popular_times:
        all_pcts = []
        for day_data in popular_times.values():
            if isinstance(day_data, list):
                for entry in day_data:
                    if isinstance(entry, dict) and "percentage" in entry:
                        all_pcts.append(entry["percentage"])
        if all_pcts:
            popularity_score = round(min(60 + max(all_pcts) * 0.4, 100.0), 1)

    # Parse reviews_json to get review count
    reviews_raw = item.get("reviews_json", "")
    review_count = 0
    if isinstance(reviews_raw, str) and reviews_raw.strip():
        try:
            reviews = json.loads(reviews_raw)
            if isinstance(reviews, list):
                review_count = len(reviews)
        except (json.JSONDecodeError, TypeError):
            pass

    # Build the class diagram item
    converted = {
        "placeId": item.get("id", ""),
        "name": item.get("name", ""),
        "description": "",  # Will be populated by generate_descriptions.py later
        "category": "ATTRACTION",
        "rating": item.get("rating", 0.0),
        "reviewCount": review_count,
        "popularityScore": popularity_score,
        "phone": item.get("phone", "") or "",
        "website": "",
        "mapsLink": item.get("maps_link", "") or "",
        "address": item.get("address", "") or "",
        "city": item.get("city", "Dubai"),
        "country": "UAE",
        "lat": item.get("latitude", item.get("location_lat", 0.0)),
        "lng": item.get("longitude", item.get("location_lng", 0.0)),
        "timezone": "Asia/Dubai",
        "photoUrls": parse_photo_urls(item.get("photo_urls", "")),
        "embedding": None,
        "hotelDetails": None,
        "restaurantDetails": None,
        "attractionDetails": {
            "placeId": item.get("id", ""),
            "attractionType": item.get("place_type", "") or "",
            "subCategory": item.get("entity_type", "") or "attraction",
            "amenities": amenities,
        },
        "openingHours": opening_hours,
    }

    return converted


def main():
    # Load source data
    print(f"Loading attractions from {SOURCE_PATH}...")
    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        attractions = json.load(f)
    print(f"  Found {len(attractions)} attractions in source")

    # Load target data
    print(f"Loading target from {TARGET_PATH}...")
    with open(TARGET_PATH, "r", encoding="utf-8") as f:
        target_data = json.load(f)
    print(f"  Found {len(target_data)} items in target")

    # Check for duplicates by placeId
    existing_ids = {item.get("placeId") for item in target_data}
    new_attractions = []
    duplicates_skipped = 0

    for attraction in attractions:
        converted = convert_attraction(attraction)
        if converted["placeId"] in existing_ids:
            duplicates_skipped += 1
            continue
        new_attractions.append(converted)
        existing_ids.add(converted["placeId"])

    print(f"  {duplicates_skipped} duplicates skipped")
    print(f"  {len(new_attractions)} new attractions to add")

    # Append to target
    target_data.extend(new_attractions)

    # Write back
    print(f"Writing merged data to {TARGET_PATH}...")
    with open(TARGET_PATH, "w", encoding="utf-8") as f:
        json.dump(target_data, f, indent=2, ensure_ascii=False)

    print(f"Done! Total items: {len(target_data)}")

    # Summary
    categories = {}
    for item in target_data:
        cat = item.get("category", "UNKNOWN")
        categories[cat] = categories.get(cat, 0) + 1
    print("\nCategory breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
