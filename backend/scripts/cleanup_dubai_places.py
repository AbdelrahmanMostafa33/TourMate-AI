"""Clean up Dubai class diagram data by removing low-quality and misclassified places.

Criteria (improved to avoid false positives on legitimate hotels/businesses):
- Places with 0 reviews AND popularityScore < 50 are likely not real tourist spots
- Places with suspicious names (event companies, corporate businesses, non-tourist services)
- Does NOT remove legitimate hotels, restaurants, or attractions
"""

import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CD_PATH = os.path.join(PROJECT_ROOT, "..", "data", "dubai", "dubai_places_class_diagram.json")

# Load data
with open(CD_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total places before cleanup: {len(data)}")

removed = []
kept = []

for place in data:
    should_remove = False
    reason = ""

    name = place.get("name", "").lower()
    category = place.get("category", "")
    review_count = place.get("reviewCount", 0)
    popularity = place.get("popularityScore", 0)
    has_description = bool(place.get("description", "").strip())
    has_phone = bool(place.get("phone", "").strip())
    has_website = bool(place.get("website", "").strip())

    # Rule 1: Remove places with 0 reviews AND low popularity (< 50)
    if review_count == 0 and popularity < 50:
        should_remove = True
        reason = "0 reviews + low popularity"

    # Rule 2: Remove event management companies (specific, not generic)
    event_patterns = [
        r"^event(s)?\s*(management|company|planning|services)",
        r"event(s)?\s+(dubai|llc|co|inc)",
        r"(event|party|conference)\s+(management|planning|organizing|services)",
    ]
    for pattern in event_patterns:
        if re.search(pattern, name):
            should_remove = True
            reason = f"Event company: {pattern}"
            break

    # Rule 3: Remove non-tourist businesses (careful not to match hotels/restaurants)
    if category != "HOTEL" and category != "RESTAURANT":
        non_tourist_patterns = [
            r"(clothing|fashion|apparel|tailor)\s*(store|shop|house)?$",
            r"^(real\s*estate|property|properties)\s",
            r"^(bank|financial|finance|insurance)\s+(group|company|services|consult)",
            r"(clinic|medical|dental|hospital|health\s*center)\s*(dubai)?$",
            r"^(gym|fitness|crossfit)\s",
            r"(salon|hair\s*salon|beauty\s*salon)\s",
            r"(car\s*(wash|service|repair|rental|dealer))\s",
            r"(phone|mobile|electronics)\s*(repair|service|shop)\s",
            r"^(supermarket|grocery|hypermarket)\s",
            r"(pet\s*(shop|store|grooming))\s",
            r"(laundry|dry\s*cleaning)\s",
            r"(printing|copy\s*shop|photo\s*studio)\s",
            r"(school|academy|training\s*center|institute|university)\s",
        ]
        for pattern in non_tourist_patterns:
            if re.search(pattern, name):
                should_remove = True
                reason = f"Non-tourist business: {pattern}"
                break

    # Rule 4: Remove very short/generic names
    if len(name) < 3:
        should_remove = True
        reason = "Name too short"

    # Rule 5: Remove places with no useful data at all
    if not has_description and not has_phone and not has_website and review_count == 0:
        should_remove = True
        reason = "No useful data (no desc, phone, website, or reviews)"

    if should_remove:
        removed.append((place, reason))
    else:
        kept.append(place)

print(f"\nRemoval summary:")
print(f"  Places to remove: {len(removed)}")
print(f"  Places to keep: {len(kept)}")

# Group removals by reason
reason_counts = {}
for place, reason in removed:
    reason_counts[reason] = reason_counts.get(reason, 0) + 1

print(f"\nRemoval reasons:")
for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {count}")

# Show sample removed entries
print(f"\nSample removed entries:")
for place, reason in removed[:15]:
    print(f"  {place['name']} ({place['category']}) - {reason}")

# Verify kept data quality
print(f"\n=== Kept Data Quality ===")
print(f"Total kept: {len(kept)}")
cats = {}
for p in kept:
    c = p.get("category", "N/A")
    cats[c] = cats.get(c, 0) + 1
print(f"Categories: {cats}")

# Check that legitimate hotels are kept
kept_hotel_names = [p["name"] for p in kept if p.get("category") == "HOTEL"]
print(f"\nSample kept hotels (first 10):")
for n in kept_hotel_names[:10]:
    print(f"  - {n}")

# Save cleaned data
with open(CD_PATH, "w", encoding="utf-8") as f:
    json.dump(kept, f, indent=2, ensure_ascii=False)

print(f"\nSaved cleaned data to: {CD_PATH}")
print(f"Removed {len(removed)} places ({len(removed)/len(data)*100:.1f}%)")
