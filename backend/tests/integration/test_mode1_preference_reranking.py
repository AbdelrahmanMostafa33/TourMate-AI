# tests/integration/test_mode1_preference_reranking.py

"""
Integration test for Mode 1 — Preference Re-Ranking.

Verifies the full "more entertaining" flow through the conversation_agent
modify handler, confirming that when the user requests a vibe change:

    1. Mode 2 (surgical modifier) is tried first — returns unchanged
    2. Mode 1 (preference re-ranking) interprets the request, adjusts
       preferences, re-ranks the existing candidate pool, and re-plans
    3. Mode 3 (full pipeline via trip_graph) is NOT invoked
    4. The response contains a newly generated itinerary
    5. The conversation state is correctly updated with the new itinerary

All external calls (LLM, Redis, OSRM, database) are mocked.
The orchestration logic in _handle_modify_itinerary and _rerank_and_replan
runs for real with mocked downstream agents.
"""

import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.chat.unified_router import RouterResult
from ai_engine.memory.conversation_state import ConversationPhase, ConversationState
from tests.integration.conftest import MOCK_PLACES


# ── Mock Helpers ───────────────────────────────────────────────────────────


def _make_result(action: str, response: str = "OK", **extracted) -> RouterResult:
    """Build a mock RouterResult."""
    return RouterResult(action=action, extracted=extracted, response=response)


def _create_session_manager():
    """Create a mock SessionManager that stores state in-memory.

    Returns (manager, storage) so tests can inspect storage directly.
    """
    storage = {}
    manager = AsyncMock()

    async def fake_resume_or_create(user_id, session_id=None):
        key = session_id or user_id
        if key not in storage:
            storage[key] = ConversationState(user_id=user_id)
        return storage[key]

    async def fake_save(state):
        storage[state.user_id] = state
        return True

    manager.resume_or_create = fake_resume_or_create
    manager.save = fake_save
    return manager, storage


def _mock_rerank_ranking(state: dict) -> dict:
    """Fake ranking agent: copies filtered_places → candidate_places."""
    state = dict(state)
    filtered = state.get("filtered_places") or []
    state["candidate_places"] = list(filtered)
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[RankingAgent] {len(filtered)} filtered → {len(filtered)} ranked candidates"]
    )
    return state


def _mock_rerank_planning(state: dict) -> dict:
    """Fake planning agent: builds a 2-day draft itinerary from candidates."""
    state = dict(state)
    candidates = state.get("candidate_places") or []
    attractions = [p for p in candidates if p.get("category") != "hotel"]
    hotels = [p for p in candidates if p.get("category") == "hotel"]

    # Pick 3 stops per day (or fewer if not enough candidates)
    stops_day1 = [
        {
            "id": a["id"],
            "name": a["name"],
            "category": a.get("category", "attraction"),
            "sub_category": a.get("sub_category", ""),
            "lat": a["lat"],
            "lon": a["lon"],
            "cuisine_type": a.get("cuisine_type", ""),
            "interest_tags": a.get("interest_tags", []),
            "why_recommended": f"Great {a.get('sub_category', 'spot')} for your trip",
            "estimated_duration_minutes": 90,
            "suggested_time_of_day": ["morning", "afternoon", "evening"][
                attractions.index(a) % 3 if a in attractions else 0
            ],
        }
        for a in attractions[:3]
    ]
    stops_day2 = [
        {
            "id": a["id"],
            "name": a["name"],
            "category": a.get("category", "attraction"),
            "sub_category": a.get("sub_category", ""),
            "lat": a["lat"],
            "lon": a["lon"],
            "cuisine_type": a.get("cuisine_type", ""),
            "interest_tags": a.get("interest_tags", []),
            "why_recommended": f"Great {a.get('sub_category', 'spot')} for day 2",
            "estimated_duration_minutes": 90,
            "suggested_time_of_day": ["morning", "afternoon", "evening"][
                (attractions.index(a) + 1) % 3 if a in attractions else 0
            ],
        }
        for a in attractions[3:6] if len(attractions) > 3
    ]

    draft = {
        "destination": state.get("destination_city", "Cairo"),
        "duration_days": state.get("duration_days", 2),
        "days": [
            {
                "day_number": 1,
                "theme": "Entertainment and Fun",
                "stops": stops_day1,
            },
            {
                "day_number": 2,
                "theme": "Cultural Exploration",
                "stops": stops_day2 or stops_day1[:2],
            },
        ],
        "accommodation_suggestions": [
            {
                "id": h["id"],
                "name": h["name"],
                "sub_category": h.get("sub_category", "hotel"),
                "lat": h["lat"],
                "lon": h["lon"],
                "why_recommended": "Comfortable stay with great amenities",
                "rating": h.get("rating", 4.0),
                "category": "hotel",
                "accommodation_type": h.get("accommodation_type", "hotel"),
                "amenities": h.get("amenities", []),
                "photos": h.get("photos", []),
            }
            for h in hotels[:2]
        ],
    }

    state["draft_itinerary"] = draft
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[Planner] {len(candidates)} candidates → 2 days, {len(stops_day1) + len(stops_day2)} stops, {len(hotels[:2])} hotels"]
    )
    return state


def _mock_rerank_optimization(state: dict) -> dict:
    """Fake optimization agent: deep-copies draft and adds travel times."""
    import copy
    state = dict(state)
    draft = state.get("draft_itinerary")
    if not draft:
        return state

    optimized = copy.deepcopy(draft)
    for day in optimized.get("days", []):
        stops = day.get("stops", [])
        for i in range(len(stops) - 1):
            stops[i]["travel_time_to_next_minutes"] = 8.0
            stops[i]["transport_mode"] = "walking"
        day["total_travel_time_minutes"] = round((len(stops) - 1) * 8.0, 1)

    state["optimized_itinerary"] = optimized
    total_travel = sum(d.get("total_travel_time_minutes", 0) for d in optimized.get("days", []))
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[Optimizer] {len(optimized.get('days', []))} days, "
           f"{sum(len(d.get('stops', [])) for d in optimized.get('days', []))} stops, "
           f"{total_travel:.0f} min total travel"]
    )
    return state


def _mock_rerank_validation(state: dict) -> dict:
    """Fake validation agent: marks itinerary as valid."""
    state = dict(state)
    state["is_valid"] = True
    state["validation"] = {
        "is_valid": True,
        "score": 85,
        "issues": [],
        "suggestions": ["Consider adding more variety in cuisine"],
    }
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + ["[Validator] valid=True score=85 issues=0"]
    )
    return state


# ── Test Data ──────────────────────────────────────────────────────────────


MOCK_ORIGINAL_ITINERARY = {
    "destination": "Cairo",
    "duration_days": 2,
    "days": [
        {
            "day_number": 1,
            "theme": "History and Culture",
            "stops": [
                {
                    "id": "place_001",
                    "name": "Egyptian Museum",
                    "category": "attractions",
                    "sub_category": "museum",
                    "lat": 30.0478, "lon": 31.2336,
                    "cuisine_type": "",
                    "interest_tags": ["history", "art", "museum"],
                    "why_recommended": "Explore ancient artifacts",
                    "estimated_duration_minutes": 120,
                    "suggested_time_of_day": "morning",
                },
                {
                    "id": "place_003",
                    "name": "Pyramids of Giza",
                    "category": "attractions",
                    "sub_category": "historic",
                    "lat": 29.9792, "lon": 31.1342,
                    "cuisine_type": "",
                    "interest_tags": ["history", "architecture", "heritage"],
                    "why_recommended": "Iconic ancient wonder",
                    "estimated_duration_minutes": 180,
                    "suggested_time_of_day": "afternoon",
                },
            ],
        },
        {
            "day_number": 2,
            "theme": "Markets and Culinary",
            "stops": [
                {
                    "id": "place_002",
                    "name": "Khan El Khalili",
                    "category": "attractions",
                    "sub_category": "market",
                    "lat": 30.0478, "lon": 31.2336,
                    "cuisine_type": "",
                    "interest_tags": ["shopping", "history", "market"],
                    "why_recommended": "Vibrant traditional market",
                    "estimated_duration_minutes": 90,
                    "suggested_time_of_day": "morning",
                },
                {
                    "id": "rest_001",
                    "name": "Abu Shukri",
                    "category": "restaurant",
                    "sub_category": "local cuisine",
                    "lat": 30.0464, "lon": 31.2325,
                    "cuisine_type": "local cuisine",
                    "interest_tags": ["food"],
                    "why_recommended": "Authentic Egyptian food",
                    "estimated_duration_minutes": 60,
                    "suggested_time_of_day": "afternoon",
                },
            ],
        },
    ],
    "accommodation_suggestions": [
        {
            "id": "hotel_001",
            "name": "Marriott Mena House",
            "sub_category": "luxury hotel",
            "lat": 29.9758, "lon": 31.1334,
            "why_recommended": "Luxury stay near pyramids",
            "rating": 4.6,
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# Integration Test — Mode 1 Preference Re-Ranking
# ═══════════════════════════════════════════════════════════════════════════


class TestMode1PreferenceReranking:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    @patch("ai_engine.chat.conversation_agent.interpret_preference_adjustment")
    @patch("ai_engine.chat.conversation_agent.run_ranking_agent")
    @patch("ai_engine.chat.conversation_agent.run_planning_agent")
    @patch("ai_engine.chat.conversation_agent.run_optimization_agent")
    @patch("ai_engine.chat.conversation_agent.run_validation_agent")
    async def test_more_entertaining_triggers_reranker(
        self,
        mock_validation,
        mock_optimization,
        mock_planning,
        mock_ranking,
        mock_reranker_llm,     # interpret_preference_adjustment
        mock_modifier,          # run_itinerary_modifier
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
    ):
        """
        User says "more entertaining" after generating an itinerary.

        Expected flow:
        1. Modifier (Mode 2) is tried — returns unchanged (identity match)
        2. Reranker LLM interprets "more entertaining" → adjustments
        3. Rerank→replan chain runs: rank → plan → optimize → validate
        4. trip_graph.ainvoke (full pipeline) is NEVER called
        5. Response contains a newly generated itinerary
        6. Conversation state is updated
        """
        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user2"}

        # Original pipeline result (only used for first itinerary generation)
        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": MOCK_PLACES,
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # ── Step 1: Generate the initial itinerary ──
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
        result1 = await handle_chat("user2", "Plan me a 2-day trip to Cairo")
        assert result1["response_type"] == "itinerary"
        assert result1["phase"] == "itinerary_review"
        assert mock_graph.ainvoke.call_count == 1  # full pipeline ran once

        # Verify state has itinerary + candidate_places
        state = storage["user2"]
        assert state.itinerary is not None
        assert state.candidate_places is not None
        assert len(state.candidate_places) == len(MOCK_PLACES)

        # ── Step 2: Set up mocks for modification ──

        # Mode 2: Modifier returns unchanged (same object identity)
        mock_modifier.return_value = state.itinerary  # same object → unchanged

        # Mode 1: Reranker LLM interprets "more entertaining"
        mock_reranker_llm.return_value = {
            "interests_add": ["entertainment", "nightlife"],
            "special_focus": "evening entertainment and shows",
            "rerank_reason": "Adding entertainment and nightlife interests boosts venues",
        }

        # Rerank chain: each agent receives state, adds its field, returns
        mock_ranking.side_effect = _mock_rerank_ranking
        mock_planning.side_effect = _mock_rerank_planning
        mock_optimization.side_effect = _mock_rerank_optimization
        mock_validation.side_effect = _mock_rerank_validation

        # ── Step 3: User requests "more entertaining" ──
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating your itinerary!",
        )

        result2 = await handle_chat("user2", "Make it more entertaining")

        # ── Step 4: Verify Mode 1 was used, NOT Mode 3 ──

        # Full pipeline should NOT have been called again
        assert mock_graph.ainvoke.call_count == 1, (
            f"Expected trip_graph.ainvoke to be called 1 time (initial generation only), "
            f"but was called {mock_graph.ainvoke.call_count} times. "
            f"Mode 1 should have short-circuited the full pipeline."
        )

        # Modifier was tried first
        assert mock_modifier.called, "Mode 2 (modifier) should have been tried first"
        assert mock_modifier.call_count == 1

        # Reranker LLM was called
        assert mock_reranker_llm.called, "Mode 1 reranker LLM should have been called"
        call_arg = mock_reranker_llm.call_args[0][0]
        assert "more entertaining" in call_arg.lower()

        # All 4 rerank chain agents were called
        assert mock_ranking.called, "Ranking agent should have been called"
        assert mock_planning.called, "Planning agent should have been called"
        assert mock_optimization.called, "Optimization agent should have been called"
        assert mock_validation.called, "Validation agent should have been called"

        # ── Step 5: Verify response structure ──
        assert result2["response_type"] == "itinerary", f"Expected itinerary, got {result2.get('response_type')}"
        assert result2["itinerary"] is not None, "Response should contain a modified itinerary"
        assert result2["itinerary"].get("destination") == "Cairo"
        assert len(result2["itinerary"].get("days", [])) > 0

        # ── Step 6: Verify state was updated ──
        updated_state = storage["user2"]
        assert updated_state.itinerary is not None
        assert updated_state.phase == ConversationPhase.ITINERARY_REVIEW
        # Candidate places should still be available for future edits
        assert updated_state.candidate_places is not None
        assert len(updated_state.candidate_places) == len(MOCK_PLACES)

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    @patch("ai_engine.chat.conversation_agent.interpret_preference_adjustment")
    @patch("ai_engine.chat.conversation_agent.run_ranking_agent")
    @patch("ai_engine.chat.conversation_agent.run_planning_agent")
    @patch("ai_engine.chat.conversation_agent.run_optimization_agent")
    @patch("ai_engine.chat.conversation_agent.run_validation_agent")
    async def test_reranker_failure_falls_through_to_pipeline(
        self,
        mock_validation,
        mock_optimization,
        mock_planning,
        mock_ranking,
        mock_reranker_llm,
        mock_modifier,
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
    ):
        """
        When Mode 1 (reranker) fails, the system falls through to
        Mode 3 (full pipeline). This verifies the fallback chain.
        """
        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user3"}
        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": MOCK_PLACES,
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate initial itinerary
        mock_route.return_value = _make_result(
            "plan_trip",
            response="Generating!",
            destination_city="Cairo", duration_days=2,
            budget_level="moderate", travel_style="cultural",
            pace="moderate", interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user3", "Plan me a 2-day Cairo trip")
        assert mock_graph.ainvoke.call_count == 1

        # Modifier returns unchanged
        mock_modifier.return_value = storage["user3"].itinerary

        # Reranker LLM returns empty (no adjustments detected)
        mock_reranker_llm.return_value = {}

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating your itinerary!",
        )
        result = await handle_chat("user3", "Make it more entertaining")

        # Full pipeline should have been called again (fallback)
        assert mock_graph.ainvoke.call_count == 2, (
            f"Expected trip_graph.ainvoke to be called 2 times (initial + fallback), "
            f"but was called {mock_graph.ainvoke.call_count} times."
        )

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    async def test_modifier_succeeds_skips_reranker_and_pipeline(
        self,
        mock_modifier,
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
    ):
        """
        When Mode 2 (surgical modifier) succeeds, both Mode 1 and
        Mode 3 are skipped. This verifies the priority ordering.
        """
        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user4"}
        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": MOCK_PLACES,
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate initial itinerary
        mock_route.return_value = _make_result(
            "plan_trip", response="Generating!",
            destination_city="Cairo", duration_days=2,
            budget_level="moderate", travel_style="cultural",
            pace="moderate", interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user4", "Plan me a 2-day Cairo trip")
        assert mock_graph.ainvoke.call_count == 1

        # Modifier returns a DIFFERENT itinerary object → success
        modified = dict(MOCK_ORIGINAL_ITINERARY)
        modified["_modifier_note"] = "Swapped hotel"
        modified["accommodation_suggestions"] = [
            {
                "id": "hotel_002", "name": "Steigenberger Tahrir",
                "sub_category": "boutique hotel",
                "lat": 30.0429, "lon": 31.2347,
                "why_recommended": "Boutique hotel in downtown",
                "rating": 4.3,
            }
        ]
        mock_modifier.return_value = modified

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating your itinerary!",
        )
        result = await handle_chat("user4", "Change the hotel to something cheaper")

        # Neither reranker nor full pipeline should have been called
        assert mock_graph.ainvoke.call_count == 1, "Full pipeline should NOT be called when modifier succeeds"
        assert result["response_type"] == "itinerary"
        assert result["itinerary"]["accommodation_suggestions"][0]["name"] == "Steigenberger Tahrir"
        assert result["phase"] == "itinerary_review"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Logging Verification — 3-Tier Fallback Chain
# ═══════════════════════════════════════════════════════════════════════════


class TestFallbackChainLogging:
    """
    Verifies that _handle_modify_itinerary emits the correct log messages
    at each stage of the 3-tier fallback chain.

    Log messages checked:
        - Mode 2 → Mode 1: "Modifier unchanged — trying preference re-ranking"
        - Mode 1 → Mode 3: "Preference re-ranking failed or no adjustments"
        - Mode 3 fallback: "Falling back to full pipeline regeneration"
    """

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    @patch("ai_engine.chat.conversation_agent.interpret_preference_adjustment")
    @patch("ai_engine.chat.conversation_agent.run_ranking_agent")
    @patch("ai_engine.chat.conversation_agent.run_planning_agent")
    @patch("ai_engine.chat.conversation_agent.run_optimization_agent")
    @patch("ai_engine.chat.conversation_agent.run_validation_agent")
    async def test_full_fallthrough_logs_all_three_modes(
        self,
        mock_validation,
        mock_optimization,
        mock_planning,
        mock_ranking,
        mock_reranker_llm,
        mock_modifier,
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
        caplog,
    ):
        """
        When both Mode 2 and Mode 1 fail, all three stages are logged:
        1. Modifier tried (Mode 2)
        2. "trying preference re-ranking" (entering Mode 1)
        3. "failed or no adjustments" (Mode 1 → Mode 3)
        4. "Falling back to full pipeline" (Mode 3)
        """
        caplog.set_level(logging.INFO)

        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user_log1"}
        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": MOCK_PLACES,
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate initial itinerary
        mock_route.return_value = _make_result(
            "plan_trip", response="Generating!",
            destination_city="Cairo", duration_days=2,
            budget_level="moderate", travel_style="cultural",
            pace="moderate", interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user_log1", "Plan me a 2-day Cairo trip")
        assert mock_graph.ainvoke.call_count == 1

        # Clear logs from initial generation
        caplog.clear()

        # Mode 2: modifier returns unchanged
        mock_modifier.return_value = storage["user_log1"].itinerary

        # Mode 1: reranker LLM returns EMPTY (no adjustments → failure)
        mock_reranker_llm.return_value = {}

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating your itinerary!",
        )
        result = await handle_chat("user_log1", "Make it more entertaining")

        # Full pipeline was invoked (Mode 3 fallback)
        assert mock_graph.ainvoke.call_count == 2
        assert result["itinerary"] is not None

        # ── Verify log sequencing ──
        log_messages = [rec.message for rec in caplog.records]
        log_text = "\n".join(log_messages)

        # All three stages should be logged
        assert "trying preference re-ranking" in log_text, (
            "Mode 1 entry should be logged when modifier is unchanged"
        )
        assert "failed or no adjustments" in log_text, (
            "Mode 1 → Mode 3 transition should be logged"
        )
        assert "Falling back to full pipeline" in log_text, (
            "Mode 3 entry should be logged"
        )

        # Verify ordering: reranker log BEFORE fallback log
        idx_reranker = log_text.index("trying preference re-ranking")
        idx_fallback = log_text.index("Falling back to full pipeline")
        assert idx_reranker < idx_fallback, (
            "Mode 1 attempt should be logged BEFORE Mode 3 fallback"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    @patch("ai_engine.chat.conversation_agent.interpret_preference_adjustment")
    @patch("ai_engine.chat.conversation_agent.run_ranking_agent")
    @patch("ai_engine.chat.conversation_agent.run_planning_agent")
    @patch("ai_engine.chat.conversation_agent.run_optimization_agent")
    @patch("ai_engine.chat.conversation_agent.run_validation_agent")
    async def test_mode1_success_no_mode3_log(
        self,
        mock_validation,
        mock_optimization,
        mock_planning,
        mock_ranking,
        mock_reranker_llm,
        mock_modifier,
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
        caplog,
    ):
        """
        When Mode 1 succeeds, Mode 3 fallback log should NOT appear.
        Only the Mode 2 → Mode 1 transition is logged.
        """
        caplog.set_level(logging.INFO)

        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user_log2"}
        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": MOCK_PLACES,
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate initial itinerary
        mock_route.return_value = _make_result(
            "plan_trip", response="Generating!",
            destination_city="Cairo", duration_days=2,
            budget_level="moderate", travel_style="cultural",
            pace="moderate", interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user_log2", "Plan me a 2-day trip to Cairo")
        assert mock_graph.ainvoke.call_count == 1

        caplog.clear()

        # Mode 2: modifier returns unchanged
        mock_modifier.return_value = storage["user_log2"].itinerary

        # Mode 1: reranker LLM returns successful adjustments
        mock_reranker_llm.return_value = {
            "interests_add": ["entertainment"],
            "rerank_reason": "Adding entertainment",
        }
        mock_ranking.side_effect = _mock_rerank_ranking
        mock_planning.side_effect = _mock_rerank_planning
        mock_optimization.side_effect = _mock_rerank_optimization
        mock_validation.side_effect = _mock_rerank_validation

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating!",
        )
        result = await handle_chat("user_log2", "Make it more entertaining")

        # Full pipeline should NOT have been called
        assert mock_graph.ainvoke.call_count == 1
        assert result["itinerary"] is not None

        # ── Verify logging ──
        log_text = "\n".join(rec.message for rec in caplog.records)

        # Mode 2 → Mode 1 transition IS logged
        assert "trying preference re-ranking" in log_text
        # Mode 3 fallback is NOT logged (Mode 1 succeeded)
        assert "Falling back to full pipeline" not in log_text, (
            "Mode 3 log should NOT appear when Mode 1 succeeds"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    @patch("ai_engine.chat.conversation_agent.interpret_preference_adjustment")
    async def test_no_candidate_places_skips_mode1_logs_mode3(
        self,
        mock_reranker_llm,
        mock_modifier,
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
        caplog,
    ):
        """
        When candidate_places is None, Mode 1 is skipped entirely.
        The system jumps from Mode 2 → Mode 3 directly.
        The reranker LLM should NOT be called.
        """
        caplog.set_level(logging.INFO)

        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user_log3"}

        # Return a pipeline result WITHOUT candidate_places
        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": None,   # ← no places for re-ranking
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate initial itinerary
        mock_route.return_value = _make_result(
            "plan_trip", response="Generating!",
            destination_city="Cairo", duration_days=2,
            budget_level="moderate", travel_style="cultural",
            pace="moderate", interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user_log3", "Plan me a 2-day Cairo trip")
        assert mock_graph.ainvoke.call_count == 1

        # Verify state has NO candidate_places
        assert storage["user_log3"].candidate_places is None

        caplog.clear()

        # Mode 2: modifier returns unchanged
        mock_modifier.return_value = storage["user_log3"].itinerary

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating!",
        )
        result = await handle_chat("user_log3", "Make it more entertaining")

        # Full pipeline was invoked (Mode 3 fallback)
        assert mock_graph.ainvoke.call_count == 2
        assert result["itinerary"] is not None

        # ── Verify logging ──
        log_text = "\n".join(rec.message for rec in caplog.records)

        # Mode 1 skip: the reranker log should NOT appear
        assert "trying preference re-ranking" not in log_text, (
            "Mode 1 should be skipped when no candidate_places available"
        )
        # Mode 3 fallback IS logged
        assert "Falling back to full pipeline" in log_text, (
            "Mode 3 should be logged when it runs"
        )

        # The reranker LLM should NOT have been called
        mock_reranker_llm.assert_not_called()

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    @patch("ai_engine.chat.conversation_agent.run_itinerary_modifier")
    async def test_modifier_success_no_mode1_nor_mode3_logs(
        self,
        mock_modifier,
        mock_profile,
        mock_graph,
        mock_route,
        mock_get_manager,
        caplog,
    ):
        """
        When Mode 2 succeeds, neither Mode 1 nor Mode 3 logs appear.
        Only the modification response is returned.
        """
        caplog.set_level(logging.INFO)

        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user_log4"}

        mock_graph.ainvoke.return_value = {
            "is_valid": True,
            "optimized_itinerary": MOCK_ORIGINAL_ITINERARY,
            "candidate_places": MOCK_PLACES,
            "agent_messages": [],
            "validation": {"is_valid": True, "score": 85},
        }

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate initial itinerary
        mock_route.return_value = _make_result(
            "plan_trip", response="Generating!",
            destination_city="Cairo", duration_days=2,
            budget_level="moderate", travel_style="cultural",
            pace="moderate", interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user_log4", "Plan me a 2-day Cairo trip")
        assert mock_graph.ainvoke.call_count == 1

        caplog.clear()

        # Mode 2: modifier returns a DIFFERENT object → success
        modified = dict(MOCK_ORIGINAL_ITINERARY)
        modified["_modifier_note"] = "Swapped hotel"
        modified["accommodation_suggestions"] = [
            {
                "id": "hotel_002", "name": "Steigenberger Tahrir",
                "sub_category": "boutique hotel",
                "lat": 30.0429, "lon": 31.2347,
                "why_recommended": "Boutique hotel",
                "rating": 4.3,
            }
        ]
        mock_modifier.return_value = modified

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating!",
        )
        result = await handle_chat("user_log4", "Change the hotel")

        # Full pipeline NOT called again
        assert mock_graph.ainvoke.call_count == 1

        # ── Verify logging: neither Mode 1 nor Mode 3 logs appear ──
        log_text = "\n".join(rec.message for rec in caplog.records)
        assert "trying preference re-ranking" not in log_text, (
            "Mode 1 should NOT be logged when modifier succeeds"
        )
        assert "Falling back to full pipeline" not in log_text, (
            "Mode 3 should NOT be logged when modifier succeeds"
        )
