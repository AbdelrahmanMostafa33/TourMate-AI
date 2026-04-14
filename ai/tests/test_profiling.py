# ai/tests/test_profiling.py

import sys
from pathlib import Path

# ── Ensure project root is in Python path ───────────────────────────
# This allows importing modules like `profiling.cold_start`
# when running the file directly (not via pytest)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profiling.cold_start import generate_persona, build_default_persona


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


if __name__ == "__main__":
    # ── Allow running tests directly without pytest ─────────────────
    # Useful for quick debugging during development
    test_generate_persona_with_gemini()
    test_default_persona()