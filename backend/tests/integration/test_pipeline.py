# tests/integration/test_pipeline.py

"""
Integration tests for the full multi-agent pipeline.

Tests verify that nodes wire together correctly through the graph:
  load_profile → retrieval → ranking → planner → optimizer → validator

All LLM calls and external services (OSRM, HTTP) are mocked,
but agent logic (scoring, filtering, routing, derivation) runs for real.

Tests cover:
  - Happy path: full pipeline produces a valid itinerary
  - Preference refinement flows into retrieval/ranking
  - Empty places causes early termination
  - LLM failure in planning causes error propagation
  - Validation failure triggers planner retry
  - Profile confidence is preserved through the pipeline
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.graph.nodes import (
    load_profile_node,
    retrieval_node,
    ranking_node,
    planning_node,
    optimization_node,
    validation_node,
)
from ai_engine.graph.edges import (
    should_rank,
    should_plan,
    should_optimize,
    should_validate,
    should_retry_or_end,
)
from ai_engine.evaluation.agent_metrics import agent_metrics
from tests.integration.conftest import (
    MOCK_PLACES,
    build_pipeline_state,
    build_planning_llm_response,
    build_validation_llm_response,
    make_mock_matrix,
)
from tests.unit.test_ai_engine.conftest import _make_profile, _make_place


# ═══════════════════════════════════════════════════════════════════════════
# 1. Happy-Path: Full Pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipelineHappyPath:
    """Each agent runs in sequence and produces valid outputs."""

    @pytest.mark.asyncio
    async def test_load_profile_passes_profile_through(self):
        """load_profile_node passes an already-loaded profile unchanged."""
        state = build_pipeline_state()
        result = await load_profile_node(state)
        assert result["profile"] is not None
        assert result["profile"]["budget_level"] == "moderate"

    @pytest.mark.asyncio
    async def test_load_profile_passes_profile_through(self):
        """load_profile_node passes an already-loaded profile unchanged."""
        state = build_pipeline_state()
        result = await load_profile_node(state)
        assert result["profile"] is not None
        assert result["profile"]["budget_level"] == "moderate"

    @pytest.mark.asyncio
    async def test_retrieval_node_filters_and_diversifies(self):
        """Place retriever loads places, filters, and ensures diversity."""
        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            result = await retrieval_node(state)

        filtered = result["filtered_places"]
        assert len(filtered) > 0
        # All returned places should have required keys
        for place in filtered:
            assert "id" in place
            assert "lat" in place
            assert "lon" in place

    @pytest.mark.asyncio
    async def test_ranking_node_scores_and_selects(self):
        """Candidate scorer scores candidates and caps the result set."""
        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)

        result = await ranking_node(state)
        candidates = result["candidate_places"]
        assert len(candidates) > 0
        assert len(candidates) <= 30  # MAX_TOTAL_CANDIDATES

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    async def test_planner_produces_draft_itinerary(self, mock_plan_llm):
        """Planning Agent produces a draft itinerary from candidates."""
        mock_plan_llm.return_value = build_planning_llm_response(num_days=2, num_stops_per_day=3)

        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        state = await ranking_node(state)

        result = await planning_node(state)
        draft = result["draft_itinerary"]
        assert draft is not None
        assert draft["destination"] == "Cairo"
        assert draft["duration_days"] == 2
        assert len(draft["days"]) == 2
        assert len(draft["accommodation_suggestions"]) >= 1

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    @patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock)
    async def test_optimizer_reorders_stops(
        self, mock_matrix, mock_plan_llm
    ):
        """Route optimizer reorders stops and annotates travel times."""
        mock_plan_llm.return_value = build_planning_llm_response(num_days=1, num_stops_per_day=3)
        mock_matrix.return_value = make_mock_matrix(3, travel_time=8.0)

        state = build_pipeline_state(duration_days=1)

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        state = await ranking_node(state)
        state = await planning_node(state)

        result = await optimization_node(state)
        optimized = result["optimized_itinerary"]
        assert optimized is not None
        assert len(optimized["days"]) == 1

        stops = optimized["days"][0]["stops"]
        assert len(stops) >= 2
        # Travel time annotations exist
        for stop in stops[:-1]:
            assert "travel_time_to_next_minutes" in stop
            assert "transport_mode" in stop

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    @patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock)
    @patch("ai_engine.services.itinerary_validator.invoke_with_fallback")
    async def test_full_pipeline_produces_valid_itinerary(
        self, mock_val_llm, mock_matrix, mock_plan_llm
    ):
        """Full pipeline: retrieval → ranking → planner → optimizer → validator."""
        mock_plan_llm.return_value = build_planning_llm_response(num_days=2, num_stops_per_day=3)
        mock_matrix.return_value = make_mock_matrix(3, travel_time=8.0)
        mock_val_llm.return_value = build_validation_llm_response(is_valid=True, score=85)

        state = build_pipeline_state()

        # Step 1: Retrieval node
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        assert len(state["filtered_places"]) > 0

        # Step 2: Ranking node
        state = await ranking_node(state)
        assert len(state["candidate_places"]) > 0

        # Step 3: Planning node
        state = await planning_node(state)
        assert state["draft_itinerary"] is not None

        # Step 4: Optimization node
        state = await optimization_node(state)
        assert state["optimized_itinerary"] is not None

        # Step 5: Validation node
        state = await validation_node(state)
        assert state["is_valid"] is True
        assert state["validation"]["score"] >= 70





# ═══════════════════════════════════════════════════════════════════════════
# 3. Error Propagation and Early Termination
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorPropagation:
    """Errors at any stage terminate the pipeline gracefully."""

    @pytest.mark.asyncio
    async def test_no_places_terminates_after_retrieval(self):
        """No places found → retrieval sets error → pipeline stops."""
        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=[]):
            state = await retrieval_node(state)

        assert state["error"] is not None
        assert state["filtered_places"] == []

        # Edge routing should go to end
        assert should_rank(state) == "end"

    @pytest.mark.asyncio
    async def test_empty_filtered_places_terminates_after_retrieval(self):
        """All places filtered out → empty filtered_places → end."""
        state = build_pipeline_state()

        # Return places that will be filtered out (low rating)
        bad_places = [_make_place(id="bad_001", name="Bad Place", rating=1.0, lat=30.0, lon=31.0)]
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=bad_places):
            state = await retrieval_node(state)

        # filtered_places might be empty after filtering
        # The edge should route to end
        edge_result = should_rank(state)
        assert edge_result == "end"

    @pytest.mark.asyncio
    async def test_no_candidates_terminates_after_ranking(self):
        """No candidates after ranking → edge routes to end."""
        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=[]):
            state = await retrieval_node(state)

        # Empty filtered_places → ranking gets nothing
        state["filtered_places"] = []
        state = await ranking_node(state)

        assert state["error"] is not None
        assert should_plan(state) == "end"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    async def test_llm_failure_in_planner_sets_error(self, mock_plan_llm):
        """Planning Agent LLM throws → error state set."""
        # Mock invoke_with_fallback to raise an exception
        mock_plan_llm.side_effect = Exception("API timeout")

        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        state = await ranking_node(state)

        result = await planning_node(state)
        assert result["error"] is not None
        assert "Planning Agent failed" in result["error"]

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    async def test_invalid_json_from_planner_sets_error(self, mock_plan_llm):
        """Planning Agent returns empty itinerary → error state set."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {"days": []}
        mock_plan_llm.return_value = mock_response

        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        state = await ranking_node(state)

        result = await planning_node(state)
        assert result["error"] is not None
        assert "Planning Agent failed" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Conditional Edge Routing
# ═══════════════════════════════════════════════════════════════════════════

class TestConditionalEdgeRouting:
    """Each edge function routes correctly based on state."""

    def test_should_rank_with_filtered_places(self):
        """Filtered places exist → route to ranking."""
        state = {"error": None, "filtered_places": [{"id": "p1"}]}
        assert should_rank(state) == "ranking"

    def test_should_rank_without_filtered_places(self):
        """No filtered places → route to end."""
        state = {"error": None, "filtered_places": []}
        assert should_rank(state) == "end"

    def test_should_rank_with_none_filtered_places(self):
        """filtered_places is None → route to end."""
        state = {"error": None, "filtered_places": None}
        assert should_rank(state) == "end"

    def test_should_plan_with_candidates(self):
        """Candidates exist → route to planner."""
        state = {"error": None, "candidate_places": [{"id": "p1"}]}
        assert should_plan(state) == "planner"

    def test_should_plan_without_candidates(self):
        """No candidates → route to end."""
        state = {"error": None, "candidate_places": []}
        assert should_plan(state) == "end"

    def test_should_optimize_without_error(self):
        """No error → route to optimizer."""
        state = {"error": None}
        assert should_optimize(state) == "optimizer"

    def test_should_optimize_with_error(self):
        """Error present → route to end."""
        state = {"error": "fail"}
        assert should_optimize(state) == "end"

    def test_should_validate_without_error(self):
        """No error → route to validator."""
        state = {"error": None}
        assert should_validate(state) == "validator"

    def test_should_retry_or_end_valid(self):
        """Valid itinerary → end."""
        state = {"is_valid": True, "error": None}
        assert should_retry_or_end(state) == "end"

    def test_should_retry_or_end_invalid_with_error(self):
        """Invalid but error present → end."""
        state = {"is_valid": False, "error": "Something wrong"}
        assert should_retry_or_end(state) == "end"

    def test_should_retry_or_end_invalid_no_error(self):
        """Invalid but no error → retry from planner."""
        state = {"is_valid": False, "error": None}
        assert should_retry_or_end(state) == "planner"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Validation Retry Flow
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# 7. Agent Metrics Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentMetricsIntegration:
    """Running all pipeline nodes should record metrics for all 6 agent roles."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    @patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock)
    @patch("ai_engine.services.itinerary_validator.invoke_with_fallback")
    async def test_all_six_roles_recorded(
        self, mock_val_llm, mock_matrix, mock_plan_llm
    ):
        """After running all 6 pipeline nodes, agent_metrics has 6 roles with non-zero calls."""
        mock_plan_llm.return_value = build_planning_llm_response(num_days=2, num_stops_per_day=3)
        mock_matrix.return_value = make_mock_matrix(3, travel_time=8.0)
        mock_val_llm.return_value = build_validation_llm_response(is_valid=True, score=85)

        # Reset metrics before the pipeline run
        agent_metrics.reset()

        state = build_pipeline_state()

        # Run all 6 nodes in sequence — load_profile_node first so all roles execute
        state = await load_profile_node(state)
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        state = await ranking_node(state)
        state = await planning_node(state)
        state = await optimization_node(state)
        state = await validation_node(state)

        # Get the summary
        summary = agent_metrics.get_summary()

        # Verify all 6 roles are present with non-zero call counts
        expected_roles = {
            "profile_loader",
            "place_retriever",
            "candidate_scorer",
            "planner",
            "route_optimizer",
            "itinerary_validator",
        }
        actual_roles = {k for k in summary if k != "total"}
        assert actual_roles == expected_roles, f"Expected roles {expected_roles}, got {actual_roles}"

        for role in expected_roles:
            row = summary[role]
            assert row["calls"] > 0, f"Role '{role}' has zero calls"
            assert row["latency_ms"]["avg"] > 0, f"Role '{role}' has zero avg latency"
            assert row["errors"] == 0, f"Role '{role}' has unexpected errors"

        # Verify total aggregation
        total = summary["total"]
        assert total["calls"] == 6, f"Expected 6 total calls, got {total['calls']}"
        assert total["errors"] == 0
        assert total["duration_ms"] > 0

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    @patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock)
    @patch("ai_engine.services.itinerary_validator.invoke_with_fallback")
    async def test_reset_between_pipeline_runs(
        self, mock_val_llm, mock_matrix, mock_plan_llm
    ):
        """Resetting agent_metrics clears data between pipeline runs."""
        mock_plan_llm.return_value = build_planning_llm_response(num_days=1, num_stops_per_day=2)
        mock_matrix.return_value = make_mock_matrix(2, travel_time=5.0)
        mock_val_llm.return_value = build_validation_llm_response(is_valid=True, score=85)

        agent_metrics.reset()
        state = build_pipeline_state(duration_days=1)

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        # Don't run full pipeline — just verify reset clears properly

        assert len(agent_metrics.get_all_snapshots()) == 1

        agent_metrics.reset()
        assert len(agent_metrics.get_all_snapshots()) == 0
        assert agent_metrics.get_summary()["total"]["calls"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_error_records_error_metric(self):
        """When an external service raises, the error is recorded in agent_metrics."""
        # Mock get_places_for_city to raise (exception propagates through retrieval_node
        # and gets caught by agent_metrics.track_async("place_retriever"))
        agent_metrics.reset()
        state = build_pipeline_state()

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, side_effect=Exception("API error")):
            with pytest.raises(Exception):
                await retrieval_node(state)

        summary = agent_metrics.get_summary()
        assert "place_retriever" in summary
        assert summary["place_retriever"]["errors"] == 1, f"Expected 1 error, got {summary['place_retriever']['errors']}"
        assert summary["place_retriever"]["calls"] == 1
        assert summary["place_retriever"]["error_rate"] > 0


class TestValidationRetryFlow:
    """When validation fails, the pipeline can retry from the planner."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.planning_agent.invoke_with_fallback")
    @patch("ai_engine.services.route_optimizer.compute_day_matrix", new_callable=AsyncMock)
    @patch("ai_engine.services.itinerary_validator.invoke_with_fallback")
    async def test_validation_failure_increments_planning_attempts(
        self, mock_val_llm, mock_matrix, mock_plan_llm
    ):
        """When validation fails, planning_attempts should be trackable."""
        mock_plan_llm.return_value = build_planning_llm_response(num_days=1, num_stops_per_day=3)
        mock_matrix.return_value = make_mock_matrix(3, travel_time=5.0)
        mock_val_llm.return_value = build_validation_llm_response(is_valid=False, score=30)

        state = build_pipeline_state(duration_days=1)

        # Run through the pipeline
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=MOCK_PLACES):
            state = await retrieval_node(state)
        state = await ranking_node(state)
        state = await planning_node(state)

        # First planning attempt
        assert state["planning_attempts"] == 1

        state = await optimization_node(state)
        state = await validation_node(state)

        # Validation failed → retry
        assert state["is_valid"] is False
        edge = should_retry_or_end(state)
        assert edge == "planner"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Profile Completeness Check
# ═══════════════════════════════════════════════════════════════════════════

class TestProfileCompleteness:
    """is_profile_complete works with the new TripProfile schema."""

    def test_complete_profile_passes(self):
        from ai_engine.tools.profile_tool import is_profile_complete
        profile = _make_profile(
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        assert is_profile_complete(profile) is True

    def test_incomplete_profile_fails(self):
        from ai_engine.tools.profile_tool import is_profile_complete
        profile = _make_profile(
            budget_level=None,
            travel_style=None,
            interests=[],
        )
        assert is_profile_complete(profile) is False

    def test_profile_to_text_contains_fields(self):
        from ai_engine.tools.profile_tool import profile_to_text
        profile = _make_profile(
            budget_level="luxury",
            travel_style="adventure",
            interests=["hiking", "diving"],
        )
        text = profile_to_text(profile)
        assert "luxury" in text
        assert "adventure" in text
        assert "hiking" in text
