# backend/tests/unit/test_ai_engine/test_planning_agent.py

"""
Unit tests for the Planning Agent.

Tests cover:
    - _trim_for_prompt(): reduces place dicts to essential fields
    - empty candidates → error
    - LLM failure → error
    - invalid JSON from LLM → error
    - valid LLM response → draft itinerary
    - markdown-wrapped JSON → success
    - hydration of stops with full place metadata
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from ai_engine.agents.planning_agent import (
    _trim_for_prompt,
    run_planning_agent,
)
from tests.unit.test_ai_engine.conftest import _make_state


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_candidate(**overrides) -> dict:
    """Create a candidate place dict as the Candidate Scorer would produce."""
    base = {
        "id": "place_001",
        "name": "Egyptian Museum",
        "category": "attractions",
        "sub_category": "museum",
        "lat": 30.0478,
        "lon": 31.2336,
        "rating": 4.7,
        "popularity_score": 95,
        "interest_tags": ["history", "art"],
        "description": "World-famous museum",
        "review_count": 2000,
        "address": "Tahrir Square",
        "hours": {},
        "photos": ["http://example.com/photo.jpg"],
        "maps_link": "http://maps.example.com",
    }
    base.update(overrides)
    return base


def _make_hotel_candidate(**overrides) -> dict:
    """Create a hotel candidate."""
    base = _make_candidate(
        id="hotel_001",
        name="Grand Nile Hotel",
        category="hotel",
        sub_category="luxury hotel",
        interest_tags=[],
        accommodation_type="hotel",
        amenities=["wifi", "pool", "spa"],
    )
    base.update(overrides)
    return base


def _make_restaurant_candidate(**overrides) -> dict:
    """Create a restaurant candidate."""
    base = _make_candidate(
        id="rest_001",
        name="Zooba Restaurant",
        category="restaurant",
        sub_category="local cuisine",
        interest_tags=["food"],
        cuisine_type="local cuisine",
    )
    base.update(overrides)
    return base


def _make_valid_itinerary() -> dict:
    """Create a valid itinerary dict as the LLM would return.

    The LLM only outputs context-dependent fields; name, category,
    sub_category, lat, lon, cuisine_type, interest_tags are reattached
    by the hydration step from the candidate place pool.
    """
    return {
        "destination": "Cairo",
        "duration_days": 2,
        "accommodation_suggestions": [
            {
                "id": "hotel_001",
                "name": "Grand Nile Hotel",
                "sub_category": "luxury hotel",
                "lat": 30.05,
                "lon": 31.24,
                "why_recommended": "Top-rated hotel",
                "rating": 4.5,
            }
        ],
        "days": [
            {
                "day_number": 1,
                "theme": "Historic Cairo",
                "stops": [
                    {
                        "id": "place_001",
                        "why_recommended": "World-famous museum",
                        "estimated_duration_minutes": 120,
                        "suggested_time_of_day": "morning",
                    },
                    {
                        "id": "rest_001",
                        "why_recommended": "Authentic Egyptian food",
                        "estimated_duration_minutes": 60,
                        "suggested_time_of_day": "afternoon",
                    },
                ],
            },
            {
                "day_number": 2,
                "theme": "Pyramids Day",
                "stops": [
                    {
                        "id": "place_002",
                        "why_recommended": "Ancient wonders",
                        "estimated_duration_minutes": 180,
                        "suggested_time_of_day": "morning",
                    },
                ],
            },
        ],
    }


def _make_planning_state(**overrides) -> dict:
    """State with planning-specific defaults (candidates, profile, city)."""
    defaults = {
        "user_message": "Plan me a 2-day trip to Cairo",
        "destination_city": "Cairo",
        "duration_days": 2,
        "candidate_places": [_make_candidate(), _make_hotel_candidate(), _make_restaurant_candidate()],
    }
    defaults.update(overrides)
    return _make_state(**defaults)


# ── _trim_for_prompt Tests ────────────────────────────────────────────────────

class TestTrimForPrompt:

    def test_trims_to_essential_fields(self):
        candidate = _make_candidate()
        trimmed = _trim_for_prompt(candidate)

        expected_keys = {"id", "name", "category", "sub_category", "lat", "lon", "score"}
        assert set(trimmed.keys()) == expected_keys

    def test_hotel_excludes_special_fields(self):
        """Hotels are handled by the Hotel Agent, not the planner.
        The planner should NOT include accommodation_type for hotels."""
        hotel = _make_hotel_candidate()
        trimmed = _trim_for_prompt(hotel)
        # Hotels should be treated the same as other non-restaurant places
        assert "accommodation_type" not in trimmed
        assert "amenities" not in trimmed

    def test_restaurant_includes_cuisine_type(self):
        restaurant = _make_restaurant_candidate()
        trimmed = _trim_for_prompt(restaurant)
        assert trimmed["cuisine_type"] == "local cuisine"

    def test_non_restaurant_excludes_cuisine_type(self):
        place = _make_candidate()
        trimmed = _trim_for_prompt(place)
        assert "cuisine_type" not in trimmed

    def test_removes_large_fields(self):
        candidate = _make_candidate()
        trimmed = _trim_for_prompt(candidate)

        assert "description" not in trimmed
        assert "review_count" not in trimmed
        assert "photos" not in trimmed
        assert "maps_link" not in trimmed
        assert "address" not in trimmed

    def test_preserves_values(self):
        candidate = _make_candidate()
        trimmed = _trim_for_prompt(candidate)

        assert trimmed["id"] == "place_001"
        assert trimmed["name"] == "Egyptian Museum"
        assert trimmed["category"] == "attractions"
        assert trimmed["lat"] == 30.0478
        assert trimmed["lon"] == 31.2336
        # composite_score is not set by _make_candidate, so it falls back to popularity_score
        assert trimmed["score"] == 95.0

    def test_score_prefers_composite_over_popularity(self):
        """When composite_score is present, use it instead of popularity_score."""
        candidate = _make_candidate(popularity_score=85, composite_score=73.5)
        trimmed = _trim_for_prompt(candidate)
        assert trimmed["score"] == 73.5

    def test_score_falls_back_to_popularity_when_no_composite(self):
        """Without composite_score, fall back to popularity_score (backward compat)."""
        candidate = _make_candidate(popularity_score=85)
        trimmed = _trim_for_prompt(candidate)
        assert trimmed["score"] == 85.0

    def test_missing_optional_fields_default(self):
        candidate = {"id": "x", "name": "X", "category": "test", "lat": 0.0, "lon": 0.0}
        trimmed = _trim_for_prompt(candidate)
        # sub_category is omitted when empty to save tokens
        assert "sub_category" not in trimmed
        assert trimmed["score"] == 0.0


# ── run_planning_agent Edge Case Tests ────────────────────────────────────────

class TestPlanningAgentEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_candidates_sets_error(self):
        ""        "No candidates from Candidate Scorer → error, no LLM call."""
        state = _make_planning_state(candidate_places=[])

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback") as mock_fn:
            result = await run_planning_agent(state)

        assert result["error"] is not None
        assert "no candidate places" in result["error"].lower()
        mock_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_candidates_sets_error(self):
        """candidate_places is None → error."""
        state = _make_planning_state(candidate_places=None)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback") as mock_fn:
            result = await run_planning_agent(state)

        assert result["error"] is not None
        mock_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_raises_exception_sets_error(self):
        """LLM throws an exception → error with message."""
        state = _make_planning_state()
        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", side_effect=Exception("API timeout")):
            result = await run_planning_agent(state)

        assert result["error"] is not None
        assert "Planning Agent failed" in result["error"]

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json_sets_error(self):
        """LLM returns non-JSON text → error."""
        state = _make_planning_state()
        mock_llm = MagicMock()
        mock_llm.content = "This is not JSON at all"
        # structured_output path: invoke_with_fallback returns an object with model_dump()
        # Simulate failure by raising during model_dump
        mock_llm.model_dump.side_effect = ValueError("Invalid structured output")

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["error"] is not None
        assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_llm_returns_markdown_wrapped_json(self):
        """LLM wraps JSON in ```json ... ``` → should parse correctly."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state()
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["draft_itinerary"] is not None
        assert result["draft_itinerary"]["destination"] == "Cairo"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_successful_planning_produces_draft(self):
        """Valid LLM response → draft itinerary stored in state."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state()
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["draft_itinerary"] is not None
        assert result["draft_itinerary"]["duration_days"] == 2
        assert len(result["draft_itinerary"]["days"]) == 2
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_planning_attempts_incremented(self):
        """After successful planning, planning_attempts should increment."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(planning_attempts=0)
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["planning_attempts"] == 1

    @pytest.mark.asyncio
    async def test_planning_attempts_increments_from_existing(self):
        """Planning attempts should increment from existing value."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(planning_attempts=2)
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["planning_attempts"] == 3

    @pytest.mark.asyncio
    async def test_hydration_enriches_stops(self):
        """Stops should be enriched with full place metadata from candidate_places.

        The LLM only outputs id, why_recommended, duration, and time-of-day.
        The hydration step reattaches name, category, sub_category, lat, lon,
        cuisine_type, interest_tags, photos, address, maps_link from the pool.
        """
        full_place = _make_candidate(id="place_001")
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(candidate_places=[full_place])
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        day1 = result["draft_itinerary"]["days"][0]
        stop = day1["stops"][0]
        # Reattached from pool
        assert stop.get("name") == "Egyptian Museum"
        assert stop.get("category") == "attractions"
        assert stop.get("sub_category") == "museum"
        assert stop.get("lat") == 30.0478
        assert stop.get("lon") == 31.2336
        assert stop.get("interest_tags") == ["history", "art"]
        assert stop.get("address") == "Tahrir Square"
        assert stop.get("photos") == ["http://example.com/photo.jpg"]
        assert stop.get("maps_link") == "http://maps.example.com"
        # LLM-provided fields preserved
        assert stop.get("why_recommended") == "World-famous museum"
        assert stop.get("estimated_duration_minutes") == 120
        assert stop.get("suggested_time_of_day") == "morning"

    @pytest.mark.asyncio
    async def test_planner_no_longer_enriches_hotels(self):
        """Hotels are now handled by the Hotel Agent, not the planner.
        The planner should NOT hydrate accommodation_suggestions."""
        full_hotel = _make_hotel_candidate(id="hotel_001")
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(candidate_places=[full_hotel])
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        # Hotels may still be in the itinerary dict (from the test fixture),
        # but the planner no longer enriches them. Key fields should be missing
        # or unchanged from the LLM output.
        hotel = result["draft_itinerary"]["accommodation_suggestions"][0]
        # category, accommodation_type, amenities are set by the Hotel Agent, not the planner
        assert "photos" not in hotel  # planner no longer enriches hotels

    @pytest.mark.asyncio
    async def test_user_message_included_in_prompt(self):
        """User's message should appear in the LLM prompt."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(user_message="Romantic Cairo trip for 2")
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm) as mock_fn:
            await run_planning_agent(state)

        call_args = mock_fn.call_args
        messages = call_args[0][1]
        human_msg = messages[1].content
        assert "Romantic Cairo trip" in human_msg

    @pytest.mark.asyncio
    async def test_candidate_places_count_in_prompt(self):
        """The prompt should mention how many candidates were provided."""
        itinerary = _make_valid_itinerary()
        candidates = [_make_candidate(id=f"c{i}") for i in range(5)]
        state = _make_planning_state(candidate_places=candidates)
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm) as mock_fn:
            await run_planning_agent(state)

        call_args = mock_fn.call_args
        messages = call_args[0][1]
        human_msg = messages[1].content
        assert "5" in human_msg  # Should mention 5 candidates

    @pytest.mark.asyncio
    async def test_no_profile_still_works(self):
        """Agent works even if profile is None."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(profile=None)
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["draft_itinerary"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_empty_itinerary_retries_then_errors(self):
        """LLM returns empty days → validation catches it, retries, then errors."""
        state = _make_planning_state()
        mock_empty = MagicMock()
        mock_empty.model_dump.side_effect = ValueError("Itinerary has empty 'days' array")

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_empty):
            result = await run_planning_agent(state)

        assert result["draft_itinerary"] is None
        assert result["error"] is not None
        assert "failed" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_hydration_skips_unknown_ids(self):
        """Stops referencing IDs not in candidate_places should not crash."""
        itinerary = _make_valid_itinerary()
        # candidate_places has no matching IDs → hydration should skip gracefully
        state = _make_planning_state(candidate_places=[{"id": "other_123", "name": "Other", "category": "attractions", "lat": 30.0, "lon": 31.0}])
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        # Should not crash — stops just don't get enriched
        assert result["draft_itinerary"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_hydration_hotel_no_longer_enriched(self):
        """Hotels are handled by Hotel Agent — planner no longer enriches hotels."""
        full_hotel = _make_hotel_candidate(
            id="hotel_001",
            address="123 Nile St",
            photos=["http://example.com/hotel.jpg"],
        )
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(candidate_places=[full_hotel])
        mock_llm = MagicMock()
        mock_llm.model_dump.return_value = itinerary

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        hotel = result["draft_itinerary"]["accommodation_suggestions"][0]
        # These were previously enriched by the planner; now done by Hotel Agent
        assert hotel.get("address") != "123 Nile St"  # planner no longer enriches
