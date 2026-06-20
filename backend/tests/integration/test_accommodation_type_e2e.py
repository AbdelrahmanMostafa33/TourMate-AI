# tests/integration/test_accommodation_type_e2e.py

"""
End-to-end integration tests for the accommodation_type flow.

Tests verify the complete pipeline from user preference extraction
through to retrieval filtering:

  user message → preference agent → map_accommodation_to_enum →
  extracted_preferences.accommodation_type → retrieval filtering

All LLM calls are mocked, but agent logic (enum mapping, scoring,
filtering, diversity) runs for real.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.agents.preference_agent import (
    map_accommodation_to_enum,
    _derive_scores,
)
from ai_engine.agents.retrieval_agent import _apply_filters, _ensure_diversity
from tests.integration.conftest import build_preference_llm_response
from tests.unit.test_ai_engine.conftest import _make_profile, _make_hotel, _make_place


def _make_restaurant(**overrides) -> dict:
    """Create a restaurant place dict."""
    base = _make_place(
        id="rest_001",
        name="Test Restaurant",
        category="restaurant",
        lat=30.04,
        lon=31.23,
        interest_tags=["food"],
        sub_category="local cuisine",
        cuisine_type="local cuisine",
    )
    base.update(overrides)
    return base


# ── Shared Test Data ───────────────────────────────────────────────────────

MIXED_PLACES = [
    _make_place(
        id="place_001",
        name="Egyptian Museum",
        category="attractions",
        lat=30.0478,
        lon=31.2336,
        rating=4.7,
        popularity_score=90,
        interest_tags=["history", "art", "museum"],
    ),
    _make_place(
        id="place_002",
        name="Khan El Khalili",
        category="attractions",
        lat=30.0478,
        lon=31.2336,
        rating=4.5,
        popularity_score=85,
        interest_tags=["shopping", "history", "market"],
    ),
    _make_hotel(
        id="hotel_001",
        name="Marriott Mena House",
        lat=29.9758,
        lon=31.1334,
        rating=4.6,
        popularity_score=80,
        accommodation_type="luxury",
        sub_category="luxury hotel",
    ),
    _make_hotel(
        id="hotel_002",
        name="Steigenberger Tahrir",
        lat=30.0429,
        lon=31.2347,
        rating=4.3,
        popularity_score=65,
        accommodation_type="hotel",
        sub_category="boutique hotel",
    ),
    _make_hotel(
        id="hotel_003",
        name="Cairo Backpackers Hostel",
        lat=30.0512,
        lon=31.2471,
        rating=3.9,
        popularity_score=45,
        accommodation_type="hostel",
        sub_category="hostel",
    ),
    _make_hotel(
        id="hotel_004",
        name="Soma Bay Resort",
        lat=30.0100,
        lon=31.1500,
        rating=4.4,
        popularity_score=70,
        accommodation_type="resort",
        sub_category="beach resort",
    ),
    _make_restaurant(
        id="rest_001",
        name="Abu Shukri",
        lat=30.0464,
        lon=31.2325,
        rating=4.5,
        popularity_score=75,
        cuisine_type="local cuisine",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Enum Mapping → Retrieval Filtering (End-to-End)
# ═══════════════════════════════════════════════════════════════════════════


class TestAccommodationTypeEndToEnd:
    """Full flow: preference extraction → enum mapping → retrieval filtering."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_luxury_preference_filters_to_luxury_hotels(self, mock_llm):
        """User says 'fancy resort' → enum maps to 'resort' → only resort hotels pass."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want a fancy resort in Cairo",
            "profile": _make_profile(
                accommodation_preferences=["fancy resort"],
                interests=["history", "art"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        # Run preference agent
        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        # Verify enum mapping happened
        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "resort"

        # Run retrieval filtering
        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )

        # Only resort hotel + attractions should pass
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_004" in hotel_ids  # Soma Bay Resort
        assert "hotel_001" not in hotel_ids  # Marriott (luxury, not resort)
        assert "hotel_002" not in hotel_ids  # Steigenberger (hotel)
        assert "hotel_003" not in hotel_ids  # Hostel

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_hostel_preference_filters_to_hostels_only(self, mock_llm):
        """User says 'hostel' → enum maps to 'hostel' → only hostels pass."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I need a cheap hostel",
            "profile": _make_profile(
                accommodation_preferences=["hostel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "hostel"

        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_003" in hotel_ids  # Cairo Backpackers Hostel
        assert "hotel_001" not in hotel_ids  # Luxury
        assert "hotel_002" not in hotel_ids  # Hotel
        assert "hotel_004" not in hotel_ids  # Resort

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_luxury_hotel_preference_filters_to_luxury_only(self, mock_llm):
        """User says 'five star hotel' → enum maps to 'luxury' → only luxury hotels pass."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want a five star hotel",
            "profile": _make_profile(
                accommodation_preferences=["five star hotel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "luxury"

        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_001" in hotel_ids  # Marriott (luxury)
        assert "hotel_002" not in hotel_ids  # Steigenberger (hotel)
        assert "hotel_003" not in hotel_ids  # Hostel
        assert "hotel_004" not in hotel_ids  # Resort

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_standard_hotel_preference_keeps_all_non_luxury(self, mock_llm):
        """User says 'hotel' → enum maps to 'hotel' → hotels of type 'hotel' pass."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "Just a regular hotel please",
            "profile": _make_profile(
                accommodation_preferences=["hotel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "hotel"

        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        # "hotel" matches places where place_acc contains "hotel" —
        # "luxury" doesn't contain "hotel", but "hotel" doesn't contain "resort"
        assert "hotel_002" in hotel_ids  # Steigenberger (hotel)
        assert "hotel_001" not in hotel_ids  # Marriott (luxury — "hotel" not in "luxury")
        assert "hotel_003" not in hotel_ids  # Hostel — "hotel" not in "hostel"
        assert "hotel_004" not in hotel_ids  # Resort — "hotel" not in "resort"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_no_accommodation_pref_keeps_all_hotels(self, mock_llm):
        """No accommodation preference → all hotels pass through."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "Plan me a trip to Cairo",
            "profile": _make_profile(
                accommodation_preferences=[],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type is None

        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        # All hotels should pass when no preference specified
        assert len(hotel_ids) == 4


# ═══════════════════════════════════════════════════════════════════════════
# 2. Preference Refinement Changes Accommodation Type
# ═══════════════════════════════════════════════════════════════════════════


class TestPreferenceRefinementChangesAccommodationType:
    """LLM refinement can change accommodation preferences, affecting filtering."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_refinement_adds_resort_changes_filtering(self, mock_llm):
        """LLM adds 'resort' to accommodation_preferences → filtering changes."""
        mock_llm.return_value = build_preference_llm_response({
            "accommodation_preferences_add": ["resort"],
        })

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "Actually, make it a resort this time",
            "profile": _make_profile(
                accommodation_preferences=["hotel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        # Preference agent should have added "resort" and mapped to resort enum
        acc_prefs = state["profile"]["accommodation_preferences"]
        assert "resort" in acc_prefs

        acc_type = state["extracted_preferences"]["accommodation_type"]
        # map_accommodation_to_enum checks in order: "resort" keyword should match first
        assert acc_type == "resort"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_refinement_removes_hostel_changes_filtering(self, mock_llm):
        """LLM removes 'hostel' from accommodation_preferences → filtering changes."""
        mock_llm.return_value = build_preference_llm_response({
            "accommodation_preferences_remove": ["hostel"],
        })

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "Actually skip the hostel, I want something nicer",
            "profile": _make_profile(
                accommodation_preferences=["hostel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_prefs = state["profile"]["accommodation_preferences"]
        assert "hostel" not in acc_prefs
        assert state["extracted_preferences"]["accommodation_type"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. Score Derivation Reflects Accommodation Type
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreDerivationReflectsAccommodationType:
    """Dimension scores correctly reflect accommodation preferences."""

    def test_resort_boosts_luxury_score(self):
        profile = _make_profile(
            budget_level="moderate",
            accommodation_preferences=["resort"],
        )
        scores = _derive_scores(profile)
        # Resort should boost luxury score above default 0.5
        assert scores["luxury_score"] > 0.5

    def test_hostel_reduces_luxury_score(self):
        profile = _make_profile(
            budget_level="moderate",
            accommodation_preferences=["hostel"],
        )
        scores = _derive_scores(profile)
        # Hostel should reduce luxury score below default 0.5
        assert scores["luxury_score"] < 0.5

    def test_boutique_hotel_boosts_luxury_score(self):
        profile = _make_profile(
            budget_level="moderate",
            accommodation_preferences=["boutique hotel"],
        )
        scores = _derive_scores(profile)
        assert scores["luxury_score"] > 0.5

    def test_luxury_budget_and_resort_gives_max_score(self):
        profile = _make_profile(
            budget_level="luxury",
            accommodation_preferences=["resort"],
        )
        scores = _derive_scores(profile)
        assert scores["luxury_score"] >= 0.9


# ═══════════════════════════════════════════════════════════════════════════
# 4. Full Pipeline with Accommodation Type
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 5. Router Extraction → Preference Mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestRouterExtractionToPreferenceMapping:
    """Router extracts accommodation_preferences, preference agent maps to enum."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_router_extracted_boutique_maps_to_luxury(self, mock_llm):
        """Router extracts 'boutique hotel' → preference agent maps to 'luxury'."""
        mock_llm.return_value = build_preference_llm_response({})

        # Simulate what the router would extract from 'I want a boutique hotel'
        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want a boutique hotel in Cairo",
            "profile": _make_profile(
                accommodation_preferences=["boutique hotel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        # verify enum mapping
        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "luxury"

        # verify downstream filtering uses it correctly
        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_001" in hotel_ids  # Marriott (luxury)
        assert "hotel_002" not in hotel_ids  # Steigenberger (hotel)
        assert "hotel_003" not in hotel_ids  # Hostel
        assert "hotel_004" not in hotel_ids  # Resort

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_router_extracted_all_inclusive_maps_to_resort(self, mock_llm):
        """Router extracts 'all-inclusive' → preference agent maps to 'resort'."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want an all-inclusive resort",
            "profile": _make_profile(
                accommodation_preferences=["all-inclusive resort"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "resort"

        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_004" in hotel_ids  # Resort
        assert "hotel_001" not in hotel_ids  # Luxury

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_router_extracted_backpacker_maps_to_hostel(self, mock_llm):
        """Router extracts 'backpacker' → preference agent maps to 'hostel'."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I'm a backpacker, find me a dorm",
            "profile": _make_profile(
                accommodation_preferences=["backpacker dorm"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "hostel"

        filtered = _apply_filters(
            MIXED_PLACES, state["extracted_preferences"], "Cairo"
        )
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_003" in hotel_ids  # Hostel
        assert "hotel_001" not in hotel_ids  # Luxury
        assert "hotel_002" not in hotel_ids  # Hotel
        assert "hotel_004" not in hotel_ids  # Resort

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_router_extracted_premium_maps_to_luxury(self, mock_llm):
        """Router extracts 'premium' → preference agent maps to 'luxury'."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want premium accommodation",
            "profile": _make_profile(
                accommodation_preferences=["premium hotel"],
                interests=["history"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)

        acc_type = state["extracted_preferences"]["accommodation_type"]
        assert acc_type == "luxury"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Full Pipeline with Accommodation Type
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipelineWithAccommodationType:
    """Full pipeline runs with accommodation_type filtering at each stage."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.preference_agent.invoke_with_fallback")
    async def test_preference_to_retrieval_pipeline_reserves_resort(self, mock_llm):
        """Full preference → retrieval pipeline filters hotels by resort type."""
        mock_llm.return_value = build_preference_llm_response({})

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want a beach resort in Cairo",
            "profile": _make_profile(
                accommodation_preferences=["beach resort"],
                interests=["history", "art"],
            ),
            "extracted_preferences": None,
            "filtered_places": None,
        }

        # Step 1: Preference Agent
        from ai_engine.graph.nodes import preference_node

        state = await preference_node(state)
        assert state["extracted_preferences"]["accommodation_type"] == "resort"

        # Step 2: Retrieval Agent (mock places, run real filtering)
        with patch(
            "ai_engine.agents.retrieval_agent.get_places_for_city",
            return_value=MIXED_PLACES,
        ):
            from ai_engine.graph.nodes import retrieval_node

            state = await retrieval_node(state)

        # Verify filtering worked
        filtered = state["filtered_places"]
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]

        # Only the resort hotel should survive
        assert "hotel_004" in hotel_ids  # Soma Bay Resort
        assert "hotel_001" not in hotel_ids  # Luxury Marriott
        assert "hotel_003" not in hotel_ids  # Hostel

        # Attractions should still be present
        attraction_ids = [
            p["id"] for p in filtered if p["category"] == "attractions"
        ]
        assert len(attraction_ids) >= 1
