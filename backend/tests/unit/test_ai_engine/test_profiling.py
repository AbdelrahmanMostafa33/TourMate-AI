# ai/tests/test_profiling.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai_engine.tools.profile_tool import load_mock_profile
from ai_engine.graph.state import TripProfile
from ai_engine.graph.graph_builder import build_trip_graph
from ai_engine.profiling.behavioral_profile import profile_to_text, is_profile_complete


def test_load_mock_profile():
    """
    Tests that load_mock_profile() returns a valid TripProfile.

    Pure unit test - no network or LLM calls.
    Validates that the mock is fully populated and structurally correct.
    """
    profile = load_mock_profile()

    assert profile["profile_id"] is not None
    assert profile["trip_id"] is not None
    assert profile["budget_level"] is not None
    assert profile["travel_pace"] is not None
    assert isinstance(profile["interests"], list)
    assert len(profile["interests"]) > 0
    assert isinstance(profile["food_preferences"], list)
    assert isinstance(profile["accommodation_preferences"], list)
    assert profile["profile_summary"] is not None
    assert profile["confidence_score"] > 0

    print(f"\nMock profile loaded: {profile['profile_summary'][:50]}...")


def test_profile_to_text():
    """
    Tests that profile_to_text() generates readable text from a TripProfile.
    """
    profile = load_mock_profile()
    text = profile_to_text(profile)

    assert "Budget: moderate" in text
    assert "Pace:" in text
    assert "Interests:" in text
    assert "Food:" in text
    assert "Accommodation:" in text
    assert "Summary:" in text

    print(f"\nProfile text:\n{text}")


def test_is_profile_complete():
    """
    Tests that is_profile_complete() correctly identifies complete vs incomplete profiles.
    """
    # Complete profile
    complete = load_mock_profile()
    assert is_profile_complete(complete) is True

    # Incomplete: no confidence
    incomplete_no_confidence = load_mock_profile()
    incomplete_no_confidence["confidence_score"] = 0.0
    assert is_profile_complete(incomplete_no_confidence) is False

    # Incomplete: no interests
    incomplete_no_interests = load_mock_profile()
    incomplete_no_interests["interests"] = []
    assert is_profile_complete(incomplete_no_interests) is False


def test_graph_runs_with_mock_profile():
    """
    End-to-end test: runs the full compiled graph using the mock profile.

    Verifies that:
    - The graph starts with load_profile_node
    - State flows through planner -> optimizer -> validator
    - Final state contains expected keys
    - No errors are raised
    """
    graph = build_trip_graph()

    initial_state = {
        "user_id": "test_user_001",
        "user_message": "Plan me a 2-day trip to Cairo",
        "profile": None,
        "token":              None,
        "trip_id":            None,
        # Preference extraction
        "extracted_preferences": None,
        # Retrieval pipeline
        "filtered_places":   None,
        "candidate_places":  None,
        # Pipeline outputs
        "draft_itinerary":     None,
        "optimized_itinerary": None,
        "is_valid":            None,
        "validation":          None,
        "planning_attempts":   0,
        # Control flow
        "next_agent": None,
        "error":      None,
        # Pre-populated intent fields
        "intent_type":         "plan_trip",
        "destination_city":    "Cairo",
        "destination_country": None,
        "duration_days":       2,
        "travel_dates":        None,
        "special_requests":    None,
        "group_size":          None,
        "missing_fields":      [],
        # Trace
        "agent_messages": [],
    }

    sample_places = [
        {"id": "h1", "name": "Grand Nile Hotel", "category": "hotel",
         "sub_category": "luxury hotel", "lat": 30.0444, "lon": 31.2357,
         "rating": 4.5, "popularity_score": 80, "interest_tags": [],
         "description": "Luxury hotel on the Nile", "review_count": 500,
         "address": "123 Nile St", "hours": {}, "photos": [], "maps_link": None},
        {"id": "h2", "name": "Budget Cairo Inn", "category": "hotel",
         "sub_category": "budget hotel", "lat": 30.05, "lon": 31.24,
         "rating": 3.8, "popularity_score": 50, "interest_tags": [],
         "description": "Affordable hotel", "review_count": 200,
         "address": "456 Main St", "hours": {}, "photos": [], "maps_link": None},
        {"id": "a1", "name": "Egyptian Museum", "category": "attractions",
         "sub_category": "museum", "lat": 30.0478, "lon": 31.2336,
         "rating": 4.7, "popularity_score": 95, "interest_tags": ["history", "art"],
         "description": "World-famous museum", "review_count": 2000,
         "address": "Tahrir Square", "hours": {}, "photos": [], "maps_link": None},
        {"id": "a2", "name": "Khan El Khalili", "category": "attractions",
         "sub_category": "market", "lat": 30.0476, "lon": 31.2611,
         "rating": 4.5, "popularity_score": 85, "interest_tags": ["history", "food"],
         "description": "Historic bazaar", "review_count": 1500,
         "address": "El Muezz St", "hours": {}, "photos": [], "maps_link": None},
        {"id": "a3", "name": "Pyramids of Giza", "category": "attractions",
         "sub_category": "historic monument", "lat": 29.9792, "lon": 31.1342,
         "rating": 4.8, "popularity_score": 100, "interest_tags": ["history"],
         "description": "Ancient wonders", "review_count": 5000,
         "address": "Al Haram", "hours": {}, "photos": [], "maps_link": None},
        {"id": "a4", "name": "Cairo Tower", "category": "attractions",
         "sub_category": "landmark", "lat": 30.0461, "lon": 31.2247,
         "rating": 4.3, "popularity_score": 70, "interest_tags": ["art"],
         "description": "Panoramic city views", "review_count": 800,
         "address": "Zamalek", "hours": {}, "photos": [], "maps_link": None},
        {"id": "r1", "name": "Zooba Egyptian Restaurant", "category": "restaurant",
         "sub_category": "local cuisine", "lat": 30.0465, "lon": 31.2288,
         "rating": 4.4, "popularity_score": 75, "interest_tags": ["food"],
         "cuisine_type": "local cuisine",
         "description": "Authentic Egyptian food", "review_count": 600,
         "address": "Zamalek", "hours": {}, "photos": [], "maps_link": None},
        {"id": "r2", "name": "Sequoia Restaurant", "category": "restaurant",
         "sub_category": "fine dining", "lat": 30.0435, "lon": 31.2275,
         "rating": 4.6, "popularity_score": 80, "interest_tags": ["food"],
         "cuisine_type": "fine dining",
         "description": "Riverside fine dining", "review_count": 400,
         "address": "Zamalek", "hours": {}, "photos": [], "maps_link": None},
        {"id": "r3", "name": "Abu Shadi Restaurant", "category": "restaurant",
         "sub_category": "local cuisine", "lat": 30.0395, "lon": 31.2110,
         "rating": 4.2, "popularity_score": 60, "interest_tags": ["food"],
         "cuisine_type": "local cuisine",
         "description": "Popular local food", "review_count": 300,
         "address": "Dokki", "hours": {}, "photos": [], "maps_link": None},
    ]

    async def _mock_get_places(city, interests=None):
        return sample_places

    import asyncio
    import unittest.mock as mock
    with mock.patch("ai_engine.agents.retrieval_agent.get_places_for_city", side_effect=_mock_get_places):
        result = asyncio.run(graph.ainvoke(initial_state))

    # Debug output
    print(f"\n--- Pipeline Debug ---")
    print(f"   Profile loaded: {result.get('profile') is not None}")
    print(f"   Budget level: {result.get('profile', {}).get('budget_level', 'N/A')}")
    print(f"   Extracted prefs: {result.get('extracted_preferences') is not None}")
    print(f"   Filtered places: {len(result.get('filtered_places') or [])}")
    print(f"   Candidate places: {len(result.get('candidate_places') or [])}")
    print(f"   Draft itinerary: {result.get('draft_itinerary') is not None}")
    print(f"   Optimized: {result.get('optimized_itinerary') is not None}")
    print(f"   Is valid: {result.get('is_valid')}")
    print(f"   Error: {result.get('error')}")
    try:
        print(f"   Agent messages: {result.get('agent_messages', [])}")
    except UnicodeEncodeError:
        print(f"   Agent messages: ({len(result.get('agent_messages', []))} messages)")
    print(f"--- End Debug ---\n")

    assert result["profile"] is not None, "Profile should be loaded by load_profile_node"
    assert result["profile"]["budget_level"] == "moderate", "Mock profile budget_level should be 'moderate'"
    assert result["draft_itinerary"] is not None, "Planner should produce a draft"
    assert result["optimized_itinerary"] is not None, "Optimizer should produce a result"
    assert result["is_valid"] is True, "Validator should mark itinerary as valid"
    assert result.get("error") is None, "No errors should occur in the happy path"


if __name__ == "__main__":
    test_load_mock_profile()
    test_profile_to_text()
    test_is_profile_complete()
    test_graph_runs_with_mock_profile()
