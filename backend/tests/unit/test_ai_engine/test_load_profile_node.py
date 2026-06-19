# tests/unit/test_ai_engine/test_load_profile_node.py

"""
Unit tests for the load_profile_node (graph entry node).

Tests cover:
    - Profile already loaded → returns state unchanged
    - No token → uses mock profile
    - Token provided → loads real profile via HTTP
    - Token provided but load fails → falls back to mock
    - Default user_id when not provided
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ai_engine.graph.nodes import load_profile_node
from tests.unit.test_ai_engine.conftest import _make_state


# ── Tests ────────────────────────────────────────────────────────────────────

class TestLoadProfileNode:

    @pytest.mark.asyncio
    async def test_profile_already_loaded_returns_unchanged(self):
        """When state already has a profile, load_profile_node is a no-op."""
        existing_profile = {"persona_name": "The Explorer", "user_id": "u1"}
        state = _make_state(profile=existing_profile)
        result = await load_profile_node(state)
        assert result["profile"] == existing_profile

    @pytest.mark.asyncio
    async def test_no_token_uses_mock_profile(self):
        """Without a token, the node falls back to the mock profile."""
        state = _make_state(profile=None, token=None)
        with patch("ai_engine.graph.nodes.load_mock_profile") as mock_load:
            mock_load.return_value = {"budget_level": "moderate", "trip_id": "t1"}
            result = await load_profile_node(state)

        mock_load.assert_called_once_with(trip_id=state.get("trip_id") or state["user_id"])
        assert result["profile"]["budget_level"] == "moderate"

    @pytest.mark.asyncio
    async def test_token_provided_loads_real_profile(self):
        """With a token, the node calls load_trip_profile."""
        real_profile = {"budget_level": "luxury", "trip_id": "t1"}
        state = _make_state(profile=None, token="valid_token")

        mock_load_real = AsyncMock(return_value=real_profile)
        with patch("ai_engine.graph.nodes.load_trip_profile", mock_load_real):
            result = await load_profile_node(state)

        mock_load_real.assert_called_once_with(trip_id=state.get("trip_id") or state["user_id"], token="valid_token")
        assert result["profile"]["budget_level"] == "luxury"

    @pytest.mark.asyncio
    async def test_real_load_failure_falls_back_to_mock(self):
        """When load_trip_profile raises, the node falls back to mock."""
        state = _make_state(profile=None, token="bad_token")

        mock_load_real = AsyncMock(side_effect=Exception("401 Unauthorized"))
        mock_load_mock = MagicMock(return_value={"budget_level": "moderate", "trip_id": "t1"})

        with patch("ai_engine.graph.nodes.load_trip_profile", mock_load_real), \
             patch("ai_engine.graph.nodes.load_mock_profile", mock_load_mock):
            result = await load_profile_node(state)

        mock_load_real.assert_called_once()
        mock_load_mock.assert_called_once_with(trip_id=state.get("trip_id") or state["user_id"])
        assert result["profile"]["budget_level"] == "moderate"

    @pytest.mark.asyncio
    async def test_default_user_id_when_key_missing(self):
        """When user_id key is missing from state, a default is used."""
        state = _make_state(profile=None, token=None)
        del state["user_id"]

        with patch("ai_engine.graph.nodes.load_mock_profile") as mock_load:
            mock_load.return_value = {"budget_level": "moderate"}
            await load_profile_node(state)

        # .get("user_id", "mock_user_001") returns default when key is absent
        mock_load.assert_called_once_with(trip_id="mock_user_001")

    @pytest.mark.asyncio
    async def test_state_is_returned(self):
        """The node always returns the state dict."""
        state = _make_state(profile=None, token=None)
        with patch("ai_engine.graph.nodes.load_mock_profile") as mock_load:
            mock_load.return_value = {"budget_level": "budget"}
            result = await load_profile_node(state)

        assert result is state
        assert result["profile"]["budget_level"] == "budget"
