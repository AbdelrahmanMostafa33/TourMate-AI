# backend/tests/unit/test_ai_engine/test_planning_agent.py

"""
Unit tests for the Planning Agent.

Tests cover:
    - _trim_for_prompt(): reduces place dicts to essential fields
    - run_planning_agent() with empty candidates → error
    - run_planning_agent() with LLM failure → error
    - run_planning_agent() with invalid JSON from LLM → error
    - run_planning_agent() with valid LLM response → draft itinerary
    - run_planning_agent() with markdown-wrapped JSON → success
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
    """Create a candidate place dict as the Ranking Agent would produce."""
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
    """Create a valid itinerary dict as the LLM would return."""
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
                        "name": "Egyptian Museum",
                        "category": "attractions",
                        "sub_category": "museum",
                        "lat": 30.0478,
                        "lon": 31.2336,
                        "why_recommended": "World-famous museum",
                        "estimated_duration_minutes": 120,
                        "suggested_time_of_day": "morning",
                    },
                    {
                        "id": "rest_001",
                        "name": "Zooba Restaurant",
                        "category": "restaurant",
                        "sub_category": "local cuisine",
                        "lat": 30.0465,
                        "lon": 31.2288,
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
                        "name": "Pyramids of Giza",
                        "category": "attractions",
                        "sub_category": "historic monument",
                        "lat": 29.9792,
                        "lon": 31.1342,
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

        expected_keys = {"id", "name", "category", "sub_category", "interest_tags", "lat", "lon", "rating", "score"}
        assert set(trimmed.keys()) == expected_keys

    def test_hotel_includes_accommodation_type(self):
        hotel = _make_hotel_candidate()
        trimmed = _trim_for_prompt(hotel)
        assert trimmed["accommodation_type"] == "hotel"
        assert trimmed["amenities"] == ["wifi", "pool", "spa"]

    def test_non_hotel_excludes_accommodation_type(self):
        place = _make_candidate()
        trimmed = _trim_for_prompt(place)
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
        assert trimmed["rating"] == 4.7

    def test_score_uses_popularity(self):
        candidate = _make_candidate(popularity_score=85)
        trimmed = _trim_for_prompt(candidate)
        assert trimmed["score"] == 85.0

    def test_missing_optional_fields_default(self):
        candidate = {"id": "x", "name": "X", "category": "test", "lat": 0.0, "lon": 0.0}
        trimmed = _trim_for_prompt(candidate)
        assert trimmed["sub_category"] == ""
        assert trimmed["rating"] == 0
        assert trimmed["score"] == 0.0


# ── run_planning_agent Edge Case Tests ────────────────────────────────────────

class TestPlanningAgentEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_candidates_sets_error(self):
        """No candidates from Ranking Agent → error, no LLM call."""
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

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["error"] is not None
        assert "Planning Agent failed" in result["error"]

    @pytest.mark.asyncio
    async def test_llm_returns_markdown_wrapped_json(self):
        """LLM wraps JSON in ```json ... ``` → should parse correctly."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state()
        mock_llm = MagicMock()
        mock_llm.content = f"```json\n{json.dumps(itinerary)}\n```"

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
        mock_llm.content = json.dumps(itinerary)

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
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["planning_attempts"] == 1

    @pytest.mark.asyncio
    async def test_planning_attempts_increments_from_existing(self):
        """Planning attempts should increment from existing value."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(planning_attempts=2)
        mock_llm = MagicMock()
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["planning_attempts"] == 3

    @pytest.mark.asyncio
    async def test_hydration_enriches_stops(self):
        """Stops should be enriched with full place metadata from candidate_places."""
        full_place = _make_candidate(id="place_001")
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(candidate_places=[full_place])
        mock_llm = MagicMock()
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        day1 = result["draft_itinerary"]["days"][0]
        stop = day1["stops"][0]
        assert stop.get("address") == "Tahrir Square"
        assert stop.get("photos") == ["http://example.com/photo.jpg"]
        assert stop.get("maps_link") == "http://maps.example.com"

    @pytest.mark.asyncio
    async def test_hydration_enriches_hotels(self):
        """Hotel suggestions should be enriched with full metadata."""
        full_hotel = _make_hotel_candidate(id="hotel_001")
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(candidate_places=[full_hotel])
        mock_llm = MagicMock()
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        hotel = result["draft_itinerary"]["accommodation_suggestions"][0]
        assert hotel.get("category") == "hotel"
        assert hotel.get("accommodation_type") == "hotel"
        assert hotel.get("amenities") == ["wifi", "pool", "spa"]

    @pytest.mark.asyncio
    async def test_user_message_included_in_prompt(self):
        """User's message should appear in the LLM prompt."""
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(user_message="Romantic Cairo trip for 2")
        mock_llm = MagicMock()
        mock_llm.content = json.dumps(itinerary)

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
        mock_llm.content = json.dumps(itinerary)

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
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["draft_itinerary"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_empty_itinerary_still_produces_draft(self):
        """LLM returns empty days → still stored as draft (downstream handles it)."""
        state = _make_planning_state()
        mock_llm = MagicMock()
        mock_llm.content = json.dumps({"destination": "Cairo", "days": [], "accommodation_suggestions": []})

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        assert result["draft_itinerary"] is not None
        assert result["draft_itinerary"]["days"] == []
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_hydration_skips_unknown_ids(self):
        """Stops referencing IDs not in candidate_places should not crash."""
        itinerary = _make_valid_itinerary()
        # candidate_places has no matching IDs → hydration should skip gracefully
        state = _make_planning_state(candidate_places=[{"id": "other_123", "name": "Other", "category": "attractions", "lat": 30.0, "lon": 31.0}])
        mock_llm = MagicMock()
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        # Should not crash — stops just don't get enriched
        assert result["draft_itinerary"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_hydration_hotel_address_and_photos(self):
        """Hotel suggestions should get address and photos from full place data."""
        full_hotel = _make_hotel_candidate(
            id="hotel_001",
            address="123 Nile St",
            photos=["http://example.com/hotel.jpg"],
        )
        itinerary = _make_valid_itinerary()
        state = _make_planning_state(candidate_places=[full_hotel])
        mock_llm = MagicMock()
        mock_llm.content = json.dumps(itinerary)

        with patch("ai_engine.agents.planning_agent.invoke_with_fallback", return_value=mock_llm):
            result = await run_planning_agent(state)

        hotel = result["draft_itinerary"]["accommodation_suggestions"][0]
        assert hotel.get("address") == "123 Nile St"
        assert hotel.get("photos") == ["http://example.com/hotel.jpg"]
