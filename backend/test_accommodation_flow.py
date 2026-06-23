"""
Validate the accommodation change flow end-to-end by testing:
1. _map_accommodation_to_type maps all accommodation types correctly
2. _apply_filters filters hotels correctly by type
3. interpret_preference_adjustment prompt examples exist for all cases
4. apply_preference_adjustments handles add/remove correctly
5. The modifier skip logic works (accommodations_updated bypasses re-rank)
"""

import sys
sys.path.insert(0, '.')

PASS = "[PASS]"
FAIL = "[FAIL]"

all_pass = True

# --- Test 1: _map_accommodation_to_type ---
from ai_engine.agents.retrieval_agent import _map_accommodation_to_type

print("=" * 60)
print("TEST 1: _map_accommodation_to_type")
print("=" * 60)

tests = [
    (["hotel"], "hotel"),
    (["boutique hotel"], "luxury"),
    (["beach resort"], "resort"),
    (["hostel"], "hostel"),
    (["backpacker hostel"], "hostel"),
    (["luxury hotel"], "luxury"),
    (["premium hotel"], "luxury"),
    (["5-star hotel"], "luxury"),
    (["airbnb apartment"], "hotel"),
    (["camping"], ""),
    ([], ""),
]

for prefs, expected in tests:
    result = _map_accommodation_to_type(prefs)
    ok = result == expected
    status = PASS if ok else FAIL
    print(f"  {status} {prefs} -> '{result}' (expected '{expected}')")
    if not ok:
        all_pass = False

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Test 2: Preference interpreter prompt has accommodation examples ---
from ai_engine.agents.preference_reranker_agent import PREFERENCE_INTERPRETER_PROMPT

print("=" * 60)
print("TEST 2: Preference Interpreter Prompt Examples")
print("=" * 60)

checks = {
    "resort example": "resorts instead of hotels" in PREFERENCE_INTERPRETER_PROMPT,
    "hostel example": "switch to hostels" in PREFERENCE_INTERPRETER_PROMPT,
    "accommodation_preferences_add field": "accommodation_preferences_add" in PREFERENCE_INTERPRETER_PROMPT,
    "accommodation_preferences_remove field": "accommodation_preferences_remove" in PREFERENCE_INTERPRETER_PROMPT,
}

for name, ok in checks.items():
    status = PASS if ok else FAIL
    print(f"  {status} {name}")
    if not ok:
        all_pass = False

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Test 3: apply_preference_adjustments handles all types ---
from ai_engine.agents.preference_reranker_agent import apply_preference_adjustments

print("=" * 60)
print("TEST 3: apply_preference_adjustments")
print("=" * 60)

class MockSlots:
    def __init__(self):
        self.interests = ["history", "food"]
        self.food_preferences = ["local cuisine"]
        self.accommodation_preferences = ["hotel"]
        self.budget_level = "moderate"
        self.travel_style = "cultural"
        self.pace = "moderate"

cases = [
    ("resorts instead of hotels", {
        "accommodation_preferences_add": ["resort"],
        "accommodation_preferences_remove": ["hotel"],
    }, ["resort"]),
    ("switch to hostels", {
        "accommodation_preferences_add": ["hostel"],
        "accommodation_preferences_remove": ["hotel"],
    }, ["hostel"]),
    ("luxury hotels", {
        "accommodation_preferences_add": ["luxury"],
        "accommodation_preferences_remove": ["hotel"],
    }, ["luxury"]),
    ("add resort keep hotel", {
        "accommodation_preferences_add": ["resort"],
        "accommodation_preferences_remove": [],
    }, ["hotel", "resort"]),
]

for name, adj, expected in cases:
    slots = MockSlots()
    result = apply_preference_adjustments(slots, adj)
    acc = result.get("accommodation_preferences", [])
    ok = set(acc) == set(expected)
    status = PASS if ok else FAIL
    print(f"  {status} {name}: {acc} (expected {expected})")
    if not ok:
        all_pass = False

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Test 4: _apply_filters hotel type matching ---
from ai_engine.agents.retrieval_agent import _apply_filters

print("=" * 60)
print("TEST 4: _apply_filters hotel type matching")
print("=" * 60)

def make_hotel(name: str, acc_type: str) -> dict:
    return {
        "id": f"test-{name}",
        "name": name,
        "category": "hotel",
        "accommodation_type": acc_type,
        "lat": 30.05,
        "lon": 31.24,
        "rating": 4.5,
        "popularity_score": 90,
    }

all_hotels = [
    make_hotel("Hotel Alpha", "hotel"),
    make_hotel("Beach Resort", "resort"),
    make_hotel("Hostel World", "hostel"),
    make_hotel("Luxury Palace", "luxury"),
]

cases = [
    ("prefer hotels -> only hotels", {"accommodation_preferences": ["hotel"]}, ["Hotel Alpha"]),
    ("prefer resorts -> only resorts", {"accommodation_preferences": ["resort"]}, ["Beach Resort"]),
    ("prefer hostels -> only hostels", {"accommodation_preferences": ["hostel"]}, ["Hostel World"]),
    ("prefer luxury -> only luxury", {"accommodation_preferences": ["luxury"]}, ["Luxury Palace"]),
    ("no preference -> all pass", {}, [h["name"] for h in all_hotels]),
]

for name, prefs, expected_names in cases:
    filtered = _apply_filters(all_hotels, prefs, "Cairo")
    actual_names = [p["name"] for p in filtered]
    ok = set(actual_names) == set(expected_names)
    status = PASS if ok else FAIL
    print(f"  {status} {name}: {actual_names}")
    if not ok:
        print(f"       expected: {expected_names}")
        all_pass = False

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Test 5: Code structure checks ---
from ai_engine.chat.conversation_agent import (
    _rerank_and_replan,
)

print("=" * 60)
print("TEST 5: Code structure checks")
print("=" * 60)

import inspect

# Check that _rerank_and_replan doesn't have the duplicate profile key
source = inspect.getsource(_rerank_and_replan)
profile_keys = 0
in_dict = False
for line in source.split('\n'):
    stripped = line.strip()
    if '"filtered_places"' in stripped:
        in_dict = True
    if in_dict and stripped == '}':
        in_dict = False
    if in_dict and stripped.startswith('"profile"'):
        profile_keys += 1

ok = profile_keys == 1
status = PASS if ok else FAIL
print(f"  {status} Duplicate profile keys in rerank_state: {profile_keys} (expected 1)")
if not ok:
    all_pass = False

# Check that apply_preference_adjustments is no longer imported in conversation_agent
from ai_engine.chat.conversation_agent import (
    interpret_preference_adjustment,
)
try:
    from ai_engine.chat.conversation_agent import apply_preference_adjustments
    print(f"  {FAIL} apply_preference_adjustments is STILL imported (should be removed)")
    all_pass = False
except ImportError:
    print(f"  {PASS} apply_preference_adjustments import was cleaned up")

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Test 6: Verify _handle_modify_itinerary skips re-rank when accommodation changes ---
print("=" * 60)
print("TEST 6: _handle_modify_itinerary skip logic")
print("=" * 60)

from ai_engine.chat.conversation_agent import _handle_modify_itinerary
source = inspect.getsource(_handle_modify_itinerary)

# Check the key logic: accommodations_updated should bypass re-ranking
checks_6 = {
    "accommodations_updated initialized before Mode 1": "accommodations_updated = False" in source,
    "skip re-rank when accommodations_updated": "accommodations_updated: True" in source or "if accommodations_updated:" in source,
    "fallback note suppressed when accommodations_updated": "not accommodations_updated" in source,
}

for name, ok in checks_6.items():
    status = PASS if ok else FAIL
    print(f"  {status} {name}")
    if not ok:
        all_pass = False

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Test 7: Verify prompt mentions both "luxury" and "resort" in keyword mapping ---
print("=" * 60)
print("TEST 7: _ACCOMMODATION_KEYWORDS coverage")
print("=" * 60)

from ai_engine.agents.retrieval_agent import _ACCOMMODATION_KEYWORDS

keyword_types = set()
for keyword, acc_type in _ACCOMMODATION_KEYWORDS:
    keyword_types.add(acc_type)

expected_types = {"hotel", "luxury", "resort", "hostel"}
missing = expected_types - keyword_types
extra = keyword_types - expected_types
ok = len(missing) == 0
status = PASS if ok else FAIL
print(f"  {status} Keyword types: {keyword_types}")
if missing:
    print(f"       Missing: {missing}")
    all_pass = False
if extra:
    print(f"       Extra (unexpected): {extra}")

# Verify specific keywords exist
keyword_checks = {
    "resort keyword": any("resort" in kw for kw, _ in _ACCOMMODATION_KEYWORDS),
    "hostel keyword": any("hostel" in kw for kw, _ in _ACCOMMODATION_KEYWORDS),
    "luxury keyword": any("luxury" in kw for kw, _ in _ACCOMMODATION_KEYWORDS),
    "boutique -> luxury": any(kw == "boutique" for kw, _ in _ACCOMMODATION_KEYWORDS),
    "5-star -> luxury": any("5-star" in kw or "five star" in kw for kw, _ in _ACCOMMODATION_KEYWORDS),
}
for name, ok in keyword_checks.items():
    status = PASS if ok else FAIL
    print(f"  {status} {name}")
    if not ok:
        all_pass = False

print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}\n")

# --- Final Result ---
print("=" * 60)
if all_pass:
    print(" ALL TESTS PASSED - accommodation change flow is correct!")
else:
    print(" SOME TESTS FAILED - see above for details")
print("=" * 60)

sys.exit(0 if all_pass else 1)
