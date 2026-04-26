# ai/tests/test_profiling.py

import sys
from pathlib import Path

# ── Ensure project root is in Python path ───────────────────────────
# This allows importing modules like `profiling.cold_start`
# when running the file directly (not via pytest)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai_engine.profiling.cold_start import generate_persona, build_default_persona
from ai_engine.tools.profile_tool import load_mock_profile
from ai_engine.graph.state import BehavioralProfile
from ai_engine.graph.graph_builder import build_trip_graph


def test_generate_persona_with_gemini():
    """
    Tests that the LLM (Gemini) generates a valid persona from quiz data.

    This is an integration-style test, not a pure unit test, because it:
    - Calls an external LLM
    - Depends on network + API availability

    Validates:
    - Required keys exist in the response
    - Suggested questions count is correct
    - Persona fields are non-empty
    """

    # ── Simulated quiz input (represents user onboarding data) ──────
    quiz_data = {
        "age": 25,
        "sex": "female",
        "travel_companion": "partner",
        "location": "Cairo",

        # Slider values (0–100 scale)
        "adventure_relaxing": 70,
        "nature_culture": 60,
        "popular_local": 40,
        "budget_level": 45,
        "early_night": 55,
        "independent_social": 50,

        # Multi-select preferences
        "accommodation_styles": ["boutique hotel", "airbnb"],
        "dining_preferences": ["local cuisine", "street food"],
        "interests": ["history", "art", "food"],
        "traveler_types": ["culture seeker", "foodie"]
    }

    # ── Call persona generation logic ───────────────────────────────
    result = generate_persona(quiz_data)

    # ── Validate structure of response ──────────────────────────────
    assert "persona_name" in result
    assert "persona_bio" in result
    assert "suggested_questions" in result

    # Ensure exactly 3 suggested questions
    assert len(result["suggested_questions"]) == 3

    # Ensure persona fields are not empty
    assert len(result["persona_name"]) > 0
    assert len(result["persona_bio"]) > 0

    # ── Debug output (useful during development) ────────────────────
    print(f"\nPersona generated:")
    print(f"   Name: {result['persona_name']}")
    print(f"   Bio:  {result['persona_bio']}")
    print(f"   Questions: {result['suggested_questions']}")


def test_default_persona():
    """
    Tests that the fallback persona is returned correctly.

    This is a pure unit test:
    - No external dependencies
    - Deterministic output

    Validates:
    - Correct persona name
    - Exactly 3 suggested questions
    """

    result = build_default_persona()

    assert result["persona_name"] == "The Open Explorer"
    assert len(result["suggested_questions"]) == 3

    print("Default persona returned correctly")


def test_load_mock_profile():
    """
    Tests that load_mock_profile() returns a valid BehavioralProfile.

    Pure unit test — no network or LLM calls.
    Validates that the mock is fully populated and structurally correct.
    """

    profile = load_mock_profile()

    assert profile["user_id"] is not None
    assert profile["quiz_completed"] is True
    assert isinstance(profile["interests"], list)
    assert len(profile["interests"]) > 0
    assert profile["persona_name"] is not None
    assert profile["persona_bio"] is not None
    assert len(profile["suggested_questions"]) == 3

    print(f"\nMock profile loaded: {profile['persona_name']}")


def test_graph_runs_with_mock_profile():
    """
    End-to-end test: runs the full compiled graph using the mock profile.

    Verifies that:
    - The graph starts with load_profile_node
    - State flows through planner → optimizer → validator
    - Final state contains expected keys
    - No errors are raised
    """

    graph = build_trip_graph()

    initial_state = {
        "user_id": "test_user_001",
        "user_message": "Plan me a 2-day trip to Cairo",
        "profile": None,
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "is_valid": None,
        "next_agent": None,
        "error": None,
        "agent_messages": [],
    }

    result = graph.invoke(initial_state)

    assert result["profile"] is not None, "Profile should be loaded by load_profile_node"
    assert result["profile"]["persona_name"] == "The Curious Culture Seeker"
    assert result["draft_itinerary"] is not None, "Planner should produce a draft"
    assert result["optimized_itinerary"] is not None, "Optimizer should produce a result"
    assert result["is_valid"] is True, "Validator should mark itinerary as valid"
    assert result.get("error") is None, "No errors should occur in the happy path"

    print(f"\nGraph ran successfully end-to-end with mock profile.")
    print(f"   Persona: {result['profile']['persona_name']}")
    print(f"   Draft status: {result['draft_itinerary']['status']}")
    print(f"   Is valid: {result['is_valid']}")


if __name__ == "__main__":
    # ── Allow running tests directly without pytest ─────────────────
    # Useful for quick debugging during development
    test_generate_persona_with_gemini()
    test_default_persona()
    test_load_mock_profile()
    test_graph_runs_with_mock_profile()