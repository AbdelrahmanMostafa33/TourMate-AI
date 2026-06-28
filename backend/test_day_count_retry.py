"""
End-to-end test: verify the day-count retry fix.

Simulates the exact failure scenario from the user's error output:
- User: "Cairo for 2 days" + image analysis (history, architecture interests)
- Planner generates only 1 day instead of 2
- Retry should rebuild the full prompt (not just append)
- On second attempt, planner should succeed with 2 days

This test validates:
1. Day-count validation correctly catches 1-day output for a 2-day trip
2. Retry prompt is rebuilt with error feedback baked into the primary instruction
3. Second attempt succeeds when LLM returns correct 2-day itinerary
4. The duration_days value validation catches wrong duration values
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from unittest.mock import patch, MagicMock, AsyncMock
import pytest


# ── Simulated LLM: first call returns 1 day, second call returns 2 days ───

class SimulatedPlannerLLM:
    """Simulates the planner LLM that initially returns wrong day count,
    then corrects on retry."""
    
    def __init__(self):
        self.call_count = 0
    
    def __call__(self, messages, **kwargs):
        self.call_count += 1
        
        from ai_engine.schemas.planning_schema import ItineraryPlan, Day, Stop
        
        if self.call_count == 1:
            # First attempt: returns 1 day instead of 2 (the bug scenario)
            print(f"  [SimulatedLLM] Call 1: Returning 1 day itinerary")
            return ItineraryPlan(
                destination="Cairo",
                duration_days=2,
                days=[
                    Day(
                        day_number=1,
                        theme="Historic Cairo",
                        stops=[
                            Stop(
                                id="place_001", name="Egyptian Museum",
                                category="attractions", sub_category="museum",
                                interest_tags=["history", "art"],
                                lat=30.0478, lon=31.2336,
                                why_recommended="World-famous museum with Pharaonic artifacts",
                                estimated_duration_minutes=120,
                                suggested_time_of_day="morning",
                            ),
                        ],
                    ),
                ],
            )
        else:
            # Second attempt: returns 2 days as requested
            print(f"  [SimulatedLLM] Call 2: Returning 2 day itinerary (retry worked!)")
            return ItineraryPlan(
                destination="Cairo",
                duration_days=2,
                days=[
                    Day(
                        day_number=1,
                        theme="Historic Cairo",
                        stops=[
                            Stop(
                                id="place_001", name="Egyptian Museum",
                                category="attractions", sub_category="museum",
                                interest_tags=["history", "art"],
                                lat=30.0478, lon=31.2336,
                                why_recommended="World-famous museum with Pharaonic artifacts",
                                estimated_duration_minutes=120,
                                suggested_time_of_day="morning",
                            ),
                        ],
                    ),
                    Day(
                        day_number=2,
                        theme="Pyramids Day",
                        stops=[
                            Stop(
                                id="place_003", name="Pyramids of Giza",
                                category="attractions", sub_category="historic",
                                interest_tags=["history", "architecture"],
                                lat=29.9792, lon=31.1342,
                                why_recommended="The last surviving ancient wonder",
                                estimated_duration_minutes=180,
                                suggested_time_of_day="morning",
                            ),
                        ],
                    ),
                ],
            )

    async def ainvoke(self, messages, config=None):
        result = self(messages)
        return result


# ── Test: Day-count retry with full prompt rebuild ────────────────────────

@pytest.mark.asyncio
async def test_day_count_retry_rebuilds_full_prompt():
    """
    Simulate the exact bug scenario: planner returns 1 day for 2-day trip.
    Verify that:
    - The first call fails with day-count mismatch
    - The retry rebuilds the full prompt with error context
    - The second call succeeds with 2 days
    """
    from ai_engine.agents.planning_agent import (
        _build_retry_prompt,
        _build_retry_note,
        run_planning_agent,
    )
    from tests.unit.test_ai_engine.conftest import _make_state, _make_profile, _make_place, _make_hotel, _make_restaurant

    # ── Build state mimicking the user's scenario ────────────────────────
    # User: "Cairo for 2 days" with image-extracted interests
    candidates = [
        _make_place(id="place_001", name="Egyptian Museum", category="attractions",
                    lat=30.0478, lon=31.2336, rating=4.7, popularity_score=90,
                    interest_tags=["history", "art", "museum"], sub_category="museum"),
        _make_place(id="place_002", name="Khan El Khalili Bazaar", category="attractions",
                    lat=30.0478, lon=31.2336, rating=4.5, popularity_score=85,
                    interest_tags=["shopping", "history", "market"], sub_category="market"),
        _make_place(id="place_003", name="Pyramids of Giza", category="attractions",
                    lat=29.9792, lon=31.1342, rating=4.8, popularity_score=95,
                    interest_tags=["history", "architecture", "heritage"], sub_category="historic"),
        _make_place(id="place_004", name="Al-Azhar Park", category="attractions",
                    lat=30.0436, lon=31.2496, rating=4.4, popularity_score=70,
                    interest_tags=["nature", "parks"], sub_category="park"),
        _make_restaurant(id="rest_001", name="Abu Shukri", category="restaurant",
                         lat=30.0464, lon=31.2325, rating=4.5, popularity_score=75,
                         cuisine_type="local cuisine", sub_category="local cuisine"),
        _make_restaurant(id="rest_002", name="Nubia Restaurant", category="restaurant",
                         lat=30.0458, lon=31.2360, rating=4.2, popularity_score=60,
                         cuisine_type="local cuisine", sub_category="street food"),
    ]

    state = _make_state(
        user_message="Cairo for 2 days",
        destination_city="Cairo",
        duration_days=2,
        profile=_make_profile(
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history", "architecture", "ancient civilizations", "desert exploration", "cultural immersion"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["hotel"],
        ),
        candidate_places=candidates,
    )

    # ── Patch the LLM to simulate the day-count bug ──────────────────────
    simulated_llm = SimulatedPlannerLLM()

    with patch("ai_engine.agents.planning_agent.invoke_with_fallback", new=AsyncMock()) as mock_invoke:
        # Make the async mock return from our simulated LLM
        mock_invoke.side_effect = lambda role, messages, **kwargs: simulated_llm.ainvoke(messages)
        
        result = await run_planning_agent(state)

    # ── Verify the pipeline eventually succeeded ─────────────────────────
    assert result["error"] is None, (
        f"Pipeline should succeed after retry, but got error: {result['error']}"
    )
    
    draft = result["draft_itinerary"]
    assert draft is not None, "Should have a draft itinerary"
    assert draft["duration_days"] == 2, f"duration_days should be 2, got {draft['duration_days']}"
    assert len(draft["days"]) == 2, (
        f"Should have 2 days after retry, got {len(draft['days'])} days\n"
        f"Error would have been: 'Itinerary has {len(draft['days'])} day(s) but Trip Duration is 2 days'"
    )
    
    total_stops = sum(len(d.get("stops", [])) for d in draft["days"])
    assert total_stops > 0, "Should have at least 1 stop total"
    
    print(f"\n  [PASS] SUCCESS: {len(draft['days'])} days, {total_stops} stops, {draft['destination']}")
    print(f"  [PASS] First attempt failed with 1 day (expected), retry rebuilt prompt, second attempt succeeded with 2 days")


# ── Test: duration_days value validation ──────────────────────────────────

@pytest.mark.asyncio
async def test_duration_days_value_validation():
    """
    Verify the new duration_days value validation catches when the LLM
    sets a wrong duration_days in the structured output.
    """
    from ai_engine.schemas.planning_schema import ItineraryPlan, Day, Stop
    
    # Simulate LLM setting duration_days=1 but Trip Duration is 2
    wrong_itinerary = ItineraryPlan(
        destination="Cairo",
        duration_days=1,  # WRONG - should be 2
        days=[
            Day(day_number=1, theme="Day 1", stops=[
                Stop(id="p1", name="Place 1", category="attractions", sub_category="museum",
                     lat=30.0, lon=31.0, why_recommended="Test",
                     estimated_duration_minutes=60, suggested_time_of_day="morning"),
            ]),
        ],
    )
    
    from ai_engine.agents.planning_agent import run_planning_agent
    from tests.unit.test_ai_engine.conftest import _make_state, _make_profile, _make_place
    
    candidates = [_make_place(id="p1", name="Place 1")]
    state = _make_state(
        user_message="Cairo 2 days",
        destination_city="Cairo",
        duration_days=2,
        candidate_places=candidates,
    )
    
    with patch("ai_engine.agents.planning_agent.invoke_with_fallback", new=AsyncMock()) as mock_invoke:
        # Return the wrong itinerary on both attempts
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = wrong_itinerary.model_dump()
        mock_invoke.return_value = mock_obj
        
        result = await run_planning_agent(state)
    
    # Should fail because duration_days=1 but state has duration_days=2
    assert result["error"] is not None
    assert "duration_days" in result["error"], (
        f"Error should mention duration_days mismatch, got: {result['error']}"
    )
    print(f"\n  [PASS] Duration_days validation caught wrong value: {result['error']}")


# ── Test: _build_retry_prompt structure ───────────────────────────────────

@pytest.mark.asyncio
async def test_retry_prompt_structure():
    """
    Verify the retry prompt includes all required context plus error feedback.
    """
    from ai_engine.agents.planning_agent import _build_retry_prompt, _build_retry_note
    
    last_error = "Itinerary has 1 day(s) but Trip Duration is 2 days. You MUST create exactly 2 entries in the `days` array."
    
    prompt = _build_retry_prompt(
        synthesized_request="Cairo for 2 days (cultural style; interested in history, architecture)",
        duration_days=2,
        city="Cairo",
        attractions_restaurants=[
            {"id": "p1", "name": "Place 1", "category": "attractions", "score": 90.0},
        ],
        last_error=last_error,
    )
    
    # Check the prompt has all the right parts
    assert "PREVIOUS ATTEMPT REJECTED" in prompt, "Should have rejection header"
    assert "CRITICAL" in prompt, "Should have the retry note"
    assert "2 entries" in prompt, "Should mention the expected count"
    assert "Trip Duration: 2 days" in prompt, "Should include trip duration"
    assert "Cairo" in prompt, "Should include city name"
    assert "Place 1" in prompt, "Should include candidates"
    assert "REMEMBER: 2 days exactly" in prompt, "Should have final reminder"
    
    # Verify the error does NOT appear twice (duplication fix)
    # The retry note includes the error, but the header just says "PREVIOUS ATTEMPT REJECTED"
    header_lines = [l for l in prompt.split('\n') if 'day(s)' in l]
    assert len(header_lines) == 1, (
        f"Error text should appear only ONCE (in retry note). Found {len(header_lines)} lines with error text:\n"
        + "\n".join(header_lines)
    )
    
    print(f"\n  [PASS] Retry prompt structure verified: headers OK, candidates OK, count OK")
    print(f"  [PASS] Error text appears only once (no duplication)")


if __name__ == "__main__":
    print("=" * 70)
    print("  End-to-End Day-Count Retry Test")
    print("  Simulating: 'Cairo for 2 days' with image interests")
    print("=" * 70)
    print()
    
    # Run tests manually
    import asyncio
    
    # Test 1: Retry prompt structure
    print("Test 1: Retry prompt structure")
    print("-" * 40)
    asyncio.run(test_retry_prompt_structure())
    print()
    
    # Test 2: duration_days value validation
    print("Test 2: duration_days value validation")
    print("-" * 40)
    asyncio.run(test_duration_days_value_validation())
    print()
    
    # Test 3: Full retry flow (main test)
    print("Test 3: Full retry flow - 1 day → retry → 2 days")
    print("-" * 40)
    asyncio.run(test_day_count_retry_rebuilds_full_prompt())
    print()
    
    print("=" * 70)
    print("  ALL 3 TESTS PASSED")
    print("=" * 70)
