"""
E2E test: Full pipeline through handle_chat with hotel agent integration.

Tests that when handle_chat triggers the full LangGraph pipeline, the
hotel_selection_node runs after the optimizer and populates
accommodation_suggestions on the final itinerary.

All external services (LLM, OSRM, database, embedding) are mocked.
The graph pipeline runs end-to-end through trip_graph.ainvoke().

NOTE: Uses context-manager ``with patch(...)`` inside test methods rather
than ``@patch`` decorators because the 11-deep decorator stack was causing
mock isolation issues with the async ``get_session_manager`` patching.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.conversation.message_interpreter import InterpretationResult
from ai_engine.conversation.conversation_state import ConversationPhase, ConversationState
from tests.integration.conftest import (
    MOCK_PLACES,
    build_planning_llm_response,
    build_validation_llm_response,
    make_mock_matrix,
)
from ai_engine.schemas.planning_schema import AccommodationSuggestion


# ── Mock Helpers ────────────────────────────────────────────────────────────


def _make_result(action: str, response: str = "OK", **extracted) -> InterpretationResult:
    """Build a mock InterpretationResult."""
    return InterpretationResult(action=action, extracted=extracted, response=response)


class _FakeSessionManager:
    """In-memory session manager (plain object with async methods).

    avoid MagicMock.__await__ traps when handle_chat does::

        manager = await get_session_manager()
        await manager.resume_or_create(...)
    """

    def __init__(self) -> None:
        self._storage: dict[str, ConversationState] = {}

    async def resume_or_create(self, user_id: str, session_id: str | None = None) -> ConversationState:
        key = session_id or user_id
        if key not in self._storage:
            self._storage[key] = ConversationState(user_id=user_id)
        return self._storage[key]

    async def save(self, state: ConversationState) -> bool:
        self._storage[state.user_id] = state
        return True

    async def extend_ttl(self, session_id: str | None = None) -> bool:
        return True


def _build_mock_hotel_selection() -> MagicMock:
    """Build a mock HotelSelection response with 2 hotels."""
    mock_response = MagicMock()
    mock_response.accommodation_suggestions = [
        AccommodationSuggestion(
            id="hotel_001",
            name="Marriott Mena House",
            sub_category="luxury hotel",
            accommodation_type="luxury",
            lat=29.9758,
            lon=31.1334,
            why_recommended="Luxury stay near the pyramids with excellent views",
            rating=4.6,
            amenities=["wifi", "pool", "spa", "restaurant"],
        ),
        AccommodationSuggestion(
            id="hotel_002",
            name="Steigenberger Tahrir",
            sub_category="boutique hotel",
            accommodation_type="boutique",
            lat=30.0429,
            lon=31.2347,
            why_recommended="Boutique hotel in downtown Cairo close to museums",
            rating=4.3,
            amenities=["wifi", "gym", "restaurant"],
        ),
    ]
    return mock_response


# ═══════════════════════════════════════════════════════════════════════════
# E2E Test — Hotel Agent via handle_chat  (context-manager patches)
# ═══════════════════════════════════════════════════════════════════════════


class TestHotelAgentE2E:
    """Verifies that the hotel_selection_node runs when handle_chat triggers
    the full graph pipeline, and that accommodation_suggestions are populated."""

    # ── helpers shared by all tests ──────────────────────────────────────

    @staticmethod
    def _session_patch(session_manager: _FakeSessionManager) -> tuple:
        """Build a context-manager patch for get_session_manager.

        Uses ``side_effect`` with an async function so both awaits in
        handle_chat (``await get_session_manager()`` and ``await
        manager.resume_or_create(…)``) resolve correctly.
        """
        async def _get_manager(*args, **kwargs):
            return session_manager
        mgr = patch(
            "ai_engine.conversation.orchestrator.get_session_manager",
            new_callable=AsyncMock,
        )
        return mgr, _get_manager, session_manager

    # ════════════════════════════════════════════════════════════════════
    # TEST 1: Hotel agent populates accommodation_suggestions
    # ════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_handle_chat_produces_hotel_suggestions(self):
        """Full pipeline via handle_chat → hotel agent populates
        accommodation_suggestions with 2 hotels."""
        session = _FakeSessionManager()

        async def _get_mgr(*args, **kwargs):
            return session

        with (
            patch("ai_engine.conversation.orchestrator.get_session_manager", new_callable=AsyncMock) as mock_get_manager,
            patch("ai_engine.conversation.orchestrator.interpret_message") as mock_route,
            patch("ai_engine.conversation.orchestrator.load_mock_profile") as mock_profile,
            patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock) as mock_places,
            patch("ai_engine.services.candidate_scorer.load_place_embeddings", return_value={}),
            patch("ai_engine.services.candidate_scorer.embed_query_async", return_value=None),
            patch("ai_engine.services.candidate_scorer._compute_semantic_interest_subcats", return_value=set()),
            patch("ai_engine.agents.planning_agent.invoke_with_fallback") as mock_plan_llm,
            patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock) as mock_matrix,
            patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_hotel_llm,
            patch("ai_engine.services.itinerary_validator.invoke_with_fallback") as mock_val_llm,
        ):
            mock_get_manager.side_effect = _get_mgr
            mock_profile.return_value = {"user_id": "e2e_hotel_test"}
            mock_places.return_value = MOCK_PLACES

            mock_plan_llm.return_value = build_planning_llm_response(
                num_days=2, num_stops_per_day=3,
            )
            mock_matrix.return_value = make_mock_matrix(3, travel_time=8.0)
            mock_hotel_llm.return_value = _build_mock_hotel_selection()
            mock_val_llm.return_value = build_validation_llm_response(
                is_valid=True, score=85,
            )

            mock_route.return_value = _make_result(
                "plan_trip",
                response="Generating your itinerary!",
                destination_city="Cairo",
                duration_days=2,
                budget_level="moderate",
                travel_style="cultural",
                pace="moderate",
                interests=["history", "art"],
                food_preferences=["local cuisine"],
                accommodation_preferences=["boutique hotel"],
            )

            from ai_engine.conversation.orchestrator import handle_chat

            result = await handle_chat(
                user_id="e2e_hotel_test",
                user_message="Plan me a 2-day trip to Cairo",
            )

        # ── Assertions ────────────────────────────────────────────────
        assert result["response_type"] == "itinerary", (
            f"Expected itinerary, got {result.get('response_type')}"
        )
        assert result["itinerary"] is not None, "No itinerary in result"
        assert result["phase"] == "itinerary_review"

        hotels = result["itinerary"].get("accommodation_suggestions", [])
        assert len(hotels) >= 1, "Expected at least 1 hotel suggestion"
        assert len(hotels) == 2, f"Expected 2 hotels, got {len(hotels)}"

        first_hotel = hotels[0]
        assert "name" in first_hotel, "Hotel missing 'name'"
        assert "id" in first_hotel, "Hotel missing 'id'"
        assert "why_recommended" in first_hotel, (
            f"Hotel '{first_hotel.get('name')}' missing 'why_recommended'"
        )
        assert first_hotel.get("why_recommended"), (
            f"Hotel '{first_hotel.get('name')}' has empty 'why_recommended'"
        )
        assert "lat" in first_hotel, "Hotel missing 'lat'"
        assert "lon" in first_hotel, "Hotel missing 'lon'"
        assert "rating" in first_hotel, "Hotel missing 'rating'"
        assert "accommodation_type" in first_hotel, (
            "Hotel missing 'accommodation_type'"
        )

        # Hotel agent uses rule-based path with ≤3 candidates (no LLM call).
        # The LLM is only invoked when >3 hotel candidates exist.
        assert mock_plan_llm.called, "Planner LLM was not called"
        assert mock_val_llm.called, "Validator LLM was not called"
        assert mock_matrix.called, "Route optimizer was not called"

        hotel_names = [h["name"] for h in hotels]
        assert "Marriott Mena House" in hotel_names, (
            f"Expected Marriott Mena House in hotels, got {hotel_names}"
        )

    # ════════════════════════════════════════════════════════════════════
    # TEST 2: No hotel candidates → empty suggestions
    # ════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_hotel_agent_empty_when_no_hotel_candidates(self):
        """When no hotels are in candidate_places, hotel agent gracefully
        returns empty accommodation_suggestions."""
        session = _FakeSessionManager()

        async def _get_mgr(*args, **kwargs):
            return session

        with (
            patch("ai_engine.conversation.orchestrator.get_session_manager", new_callable=AsyncMock) as mock_get_manager,
            patch("ai_engine.conversation.orchestrator.interpret_message") as mock_route,
            patch("ai_engine.conversation.orchestrator.load_mock_profile") as mock_profile,
            patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock) as mock_places,
            patch("ai_engine.services.candidate_scorer.load_place_embeddings", return_value={}),
            patch("ai_engine.services.candidate_scorer.embed_query_async", return_value=None),
            patch("ai_engine.services.candidate_scorer._compute_semantic_interest_subcats", return_value=set()),
            patch("ai_engine.agents.planning_agent.invoke_with_fallback") as mock_plan_llm,
            patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock) as mock_matrix,
            patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_hotel_llm,
            patch("ai_engine.services.itinerary_validator.invoke_with_fallback") as mock_val_llm,
        ):
            mock_get_manager.side_effect = _get_mgr
            mock_profile.return_value = {"user_id": "e2e_no_hotels"}

            non_hotel_places = [p for p in MOCK_PLACES if p.get("category") != "hotel"]
            mock_places.return_value = non_hotel_places

            mock_plan_llm.return_value = build_planning_llm_response(
                num_days=2, num_stops_per_day=3,
            )
            mock_matrix.return_value = make_mock_matrix(3, travel_time=8.0)
            mock_hotel_llm.return_value = _build_mock_hotel_selection()
            mock_val_llm.return_value = build_validation_llm_response(
                is_valid=True, score=85,
            )

            mock_route.return_value = _make_result(
                "plan_trip",
                response="Generating your itinerary!",
                destination_city="Cairo",
                duration_days=2,
                budget_level="moderate",
                travel_style="cultural",
                pace="moderate",
                interests=["history", "art"],
                food_preferences=["local cuisine"],
                accommodation_preferences=["boutique hotel"],
            )

            from ai_engine.conversation.orchestrator import handle_chat

            result = await handle_chat(
                user_id="e2e_no_hotels",
                user_message="Plan me a 2-day trip to Cairo",
            )

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None

        hotels = result["itinerary"].get("accommodation_suggestions", [])
        assert len(hotels) == 0, (
            f"Expected 0 hotels when no hotel candidates, got {len(hotels)}: "
            f"{[h.get('name') for h in hotels]}"
        )

    # ════════════════════════════════════════════════════════════════════
    # TEST 3: Hotel agent fallback when LLM fails
    # ════════════════════════════════════════════════════════════════════

    @pytest.mark.asyncio
    async def test_hotel_agent_fallback_when_llm_fails(self):
        """When hotel agent LLM fails, it falls back to rule-based selection
        and still populates accommodation_suggestions."""
        session = _FakeSessionManager()

        async def _get_mgr(*args, **kwargs):
            return session

        with (
            patch("ai_engine.conversation.orchestrator.get_session_manager", new_callable=AsyncMock) as mock_get_manager,
            patch("ai_engine.conversation.orchestrator.interpret_message") as mock_route,
            patch("ai_engine.conversation.orchestrator.load_mock_profile") as mock_profile,
            patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock) as mock_places,
            patch("ai_engine.services.candidate_scorer.load_place_embeddings", return_value={}),
            patch("ai_engine.services.candidate_scorer.embed_query_async", return_value=None),
            patch("ai_engine.services.candidate_scorer._compute_semantic_interest_subcats", return_value=set()),
            patch("ai_engine.agents.planning_agent.invoke_with_fallback") as mock_plan_llm,
            patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock) as mock_matrix,
            patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_hotel_llm,
            patch("ai_engine.services.itinerary_validator.invoke_with_fallback") as mock_val_llm,
        ):
            mock_get_manager.side_effect = _get_mgr
            mock_profile.return_value = {"user_id": "e2e_fallback_test"}
            mock_places.return_value = MOCK_PLACES

            mock_plan_llm.return_value = build_planning_llm_response(
                num_days=2, num_stops_per_day=3,
            )
            mock_matrix.return_value = make_mock_matrix(3, travel_time=8.0)

            # Hotel agent LLM fails → triggers rule-based fallback
            mock_hotel_llm.side_effect = Exception("Hotel LLM API error")

            mock_val_llm.return_value = build_validation_llm_response(
                is_valid=True, score=85,
            )

            mock_route.return_value = _make_result(
                "plan_trip",
                response="Generating your itinerary!",
                destination_city="Cairo",
                duration_days=2,
                budget_level="moderate",
                travel_style="cultural",
                pace="moderate",
                interests=["history", "art"],
                food_preferences=["local cuisine"],
                accommodation_preferences=["boutique hotel"],
            )

            from ai_engine.conversation.orchestrator import handle_chat

            result = await handle_chat(
                user_id="e2e_fallback_test",
                user_message="Plan me a 2-day trip to Cairo",
            )

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None

        hotels = result["itinerary"].get("accommodation_suggestions", [])
        assert len(hotels) >= 1, (
            f"Expected at least 1 hotel from fallback, got {len(hotels)}"
        )
        for hotel in hotels:
            assert "why_recommended" in hotel, (
                f"Fallback hotel '{hotel.get('name')}' missing why_recommended"
            )
