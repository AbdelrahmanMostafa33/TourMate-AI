"""
Unit tests for ``update_traveler_persona()`` — requirement #08.

Tests the AI-driven persona update flow:
  1. Loads user + TripProfile for the given trip
  2. Calls ``PreferenceTracker.merge()`` with profile data
  3. Calls ``persona_updater.update_persona()`` (LLM)
  4. Persists ``traveler_persona`` + ``preference_counts``

All external dependencies (LLM, preference tracker) are mocked.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.profile import TripProfile
from app.models.enums import BudgetLevel, TravelStyle, TripPace
from app.services.profile_service import update_traveler_persona


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock async session.

    ``mock_db.execute`` always returns the same ``mock_result``.
    To vary what ``scalar_one_or_none`` returns across successive calls,
    tests set ``mock_result.scalar_one_or_none.side_effect = [user, profile]``.
    """
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _mock_user(user_id: str = "test_user", existing_persona: str | None = None) -> MagicMock:
    """Create a User ORM mock with the given persona."""
    user = MagicMock(spec=User)
    user.user_id = user_id
    user.traveler_persona = existing_persona
    user.preference_counts = {"budget": {"budget": 1, "moderate": 2, "luxury": 0}}
    return user


def _mock_trip_profile() -> MagicMock:
    """Create a TripProfile ORM mock with all fields populated."""
    profile = MagicMock(spec=TripProfile)
    profile.budget_level = BudgetLevel.MODERATE
    profile.travel_style = TravelStyle.CULTURAL
    profile.pace = TripPace.MODERATE
    profile.interests = ["history", "art", "food"]
    profile.food_preferences = ["local cuisine", "street food"]
    profile.accommodation_preferences = ["boutique hotel"]
    profile.generated_at = datetime(2026, 7, 1)
    profile.updated_at = datetime(2026, 7, 4)
    return profile


def _configure_execute(mock_db, results: list) -> None:
    """Configure ``mock_db.execute`` so successive calls return different scalar values.

    IMPORTANT: Use ``MagicMock`` (not ``AsyncMock``) for the result object
    because ``scalar_one_or_none()`` is a **synchronous** method.
    ``AsyncMock`` would make EVERY method call return a coroutine, which
    breaks sync method access.

    ``mock_db.execute`` (which IS async) always returns the same
    ``MagicMock`` result object.  Successive calls to the sync
    ``scalar_one_or_none()`` method iterate through ``results`` via
    ``side_effect``.
    """
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.side_effect = results
    mock_db.execute.return_value = result_mock


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUpdateTravelerPersonaService:
    """Unit tests for ``update_traveler_persona()`` — the AI-driven persona update."""

    async def test_updates_persona_from_trip_profile(self, mock_db):
        """Happy path: user + TripProfile exist → LLM returns new persona → user is updated."""
        user = _mock_user(existing_persona="A casual traveler.")
        profile = _mock_trip_profile()

        # Configure execute: first call returns user, second returns profile
        _configure_execute(mock_db, [user, profile])

        # ── Patch local imports ──────────────────────────────────────────
        # update_traveler_persona() has local imports inside the function:
        #   from ai_engine.profiling.preference_tracker import PreferenceTracker
        #   from ai_engine.profiling.persona_updater import update_persona as _llm_update_persona
        # Patch the ORIGINAL module paths, not app.services.profile_service.
        with patch(
            "ai_engine.profiling.preference_tracker.PreferenceTracker"
        ) as mock_tracker_cls, patch(
            "ai_engine.profiling.persona_updater.update_persona",
            new_callable=AsyncMock,
        ) as mock_llm:

            mock_tracker = mock_tracker_cls.return_value
            mock_tracker.merge.return_value = {
                "budget": {"budget": 1, "moderate": 3, "luxury": 0},
            }

            mock_llm.return_value = (
                "A moderately-paced cultural traveler who loves history, "
                "art, and local cuisine, with a growing preference for boutique hotels."
            )

            result = await update_traveler_persona(
                user_id="test_user",
                trip_id="test_trip",
                db=mock_db,
            )

        # ── Assertions ──────────────────────────────────────────────────
        assert result is not None
        assert "cultural" in result.lower()
        assert "local cuisine" in result.lower()
        assert "boutique" in result.lower()

        # Verify user was updated
        assert user.traveler_persona == result
        assert user.preference_counts == {
            "budget": {"budget": 1, "moderate": 3, "luxury": 0},
        }

        # Verify DB was committed and refreshed
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(user)

        # Verify LLM was called with correct data
        mock_llm.assert_awaited_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["old_persona"] == "A casual traveler."
        assert call_kwargs["trip_profile_data"]["budget_level"] == BudgetLevel.MODERATE
        assert call_kwargs["trip_profile_data"]["travel_style"] == TravelStyle.CULTURAL
        assert call_kwargs["trip_profile_data"]["pace"] == TripPace.MODERATE
        assert "history" in call_kwargs["trip_profile_data"]["interests"]
        assert "local cuisine" in call_kwargs["trip_profile_data"]["food_preferences"]
        assert "boutique hotel" in call_kwargs["trip_profile_data"]["accommodation_preferences"]

    async def test_skips_when_no_trip_profile(self, mock_db):
        """No TripProfile for the trip → returns None (skips)."""
        user = _mock_user(existing_persona="Some persona.")

        # First query returns user, second returns None (no TripProfile)
        _configure_execute(mock_db, [user, None])

        result = await update_traveler_persona(
            user_id="test_user",
            trip_id="test_trip",
            db=mock_db,
        )

        assert result is None
        mock_db.commit.assert_not_called()

    async def test_skips_when_user_not_found(self, mock_db):
        """User not in DB → returns None."""
        # First query returns None (no user) — second never reached
        _configure_execute(mock_db, [None])

        result = await update_traveler_persona(
            user_id="nonexistent_user",
            trip_id="test_trip",
            db=mock_db,
        )

        assert result is None
        mock_db.commit.assert_not_called()

    async def test_returns_none_when_llm_returns_none(self, mock_db):
        """LLM returns None → returns None (keeps old persona)."""
        user = _mock_user(existing_persona="Keep this persona.")
        profile = _mock_trip_profile()

        _configure_execute(mock_db, [user, profile])

        with patch(
            "ai_engine.profiling.preference_tracker.PreferenceTracker"
        ) as mock_tracker_cls, patch(
            "ai_engine.profiling.persona_updater.update_persona",
            new_callable=AsyncMock,
        ) as mock_llm:

            mock_tracker_cls.return_value.merge.return_value = {}
            mock_llm.return_value = None

            result = await update_traveler_persona(
                user_id="test_user",
                trip_id="test_trip",
                db=mock_db,
            )

        assert result is None
        # Persona should be unchanged
        assert user.traveler_persona == "Keep this persona."
        # DB should NOT be committed
        mock_db.commit.assert_not_called()

    async def test_persona_unchanged_but_counts_updated(self, mock_db):
        """LLM returns same text → persona unchanged, but preference_counts still updated."""
        user = _mock_user(existing_persona="An unchanged persona.")
        profile = _mock_trip_profile()

        _configure_execute(mock_db, [user, profile])

        merged_counts = {
            "budget": {"budget": 1, "moderate": 4, "luxury": 0},
        }

        with patch(
            "ai_engine.profiling.preference_tracker.PreferenceTracker"
        ) as mock_tracker_cls, patch(
            "ai_engine.profiling.persona_updater.update_persona",
            new_callable=AsyncMock,
        ) as mock_llm:

            mock_tracker_cls.return_value.merge.return_value = merged_counts
            mock_llm.return_value = "An unchanged persona."  # same as existing

            result = await update_traveler_persona(
                user_id="test_user",
                trip_id="test_trip",
                db=mock_db,
            )

        # Persona text is returned (unchanged)
        assert result == "An unchanged persona."
        # Preference counts ARE updated
        assert user.preference_counts == merged_counts
        # DB was committed (counts changed even though persona didn't)
        mock_db.commit.assert_called_once()

    async def test_updates_persona_when_old_persona_is_none(self, mock_db):
        """Starting with no persona → LLM creates one from trip data."""
        user = _mock_user(existing_persona=None)
        profile = _mock_trip_profile()

        _configure_execute(mock_db, [user, profile])

        with patch(
            "ai_engine.profiling.preference_tracker.PreferenceTracker"
        ) as mock_tracker_cls, patch(
            "ai_engine.profiling.persona_updater.update_persona",
            new_callable=AsyncMock,
        ) as mock_llm:

            mock_tracker_cls.return_value.merge.return_value = {}
            mock_llm.return_value = (
                "A first-time traveler interested in history, art, and local cuisine."
            )

            result = await update_traveler_persona(
                user_id="test_user",
                trip_id="test_trip",
                db=mock_db,
            )

        assert result is not None
        assert "first-time" in result.lower()
        assert user.traveler_persona == result
        mock_db.commit.assert_called_once()

        # Verify LLM was called with None old_persona
        assert mock_llm.call_args.kwargs["old_persona"] is None

    async def test_passes_all_trip_profile_fields_to_llm(self, mock_db):
        """All TripProfile fields are correctly passed to the LLM."""
        user = _mock_user(existing_persona="A test persona.")
        profile = _mock_trip_profile()

        _configure_execute(mock_db, [user, profile])

        with patch(
            "ai_engine.profiling.preference_tracker.PreferenceTracker"
        ) as mock_tracker_cls, patch(
            "ai_engine.profiling.persona_updater.update_persona",
            new_callable=AsyncMock,
        ) as mock_llm:

            mock_tracker_cls.return_value.merge.return_value = {}
            mock_llm.return_value = "Updated."

            await update_traveler_persona(
                user_id="test_user",
                trip_id="test_trip",
                db=mock_db,
            )

        profile_data = mock_llm.call_args.kwargs["trip_profile_data"]
        assert profile_data["budget_level"] == BudgetLevel.MODERATE
        assert profile_data["travel_style"] == TravelStyle.CULTURAL
        assert profile_data["pace"] == TripPace.MODERATE
        assert profile_data["interests"] == ["history", "art", "food"]
        assert profile_data["food_preferences"] == ["local cuisine", "street food"]
        assert profile_data["accommodation_preferences"] == ["boutique hotel"]

    async def test_preference_counts_are_merged_and_passed(self, mock_db):
        """PreferenceTracker.merge is called with old counts + profile data,
        and the merged counts are passed to the LLM."""
        user = _mock_user(existing_persona="Test persona.")
        profile = _mock_trip_profile()

        _configure_execute(mock_db, [user, profile])

        merged = {"budget": {"budget": 0, "moderate": 5, "luxury": 1}}

        with patch(
            "ai_engine.profiling.preference_tracker.PreferenceTracker"
        ) as mock_tracker_cls, patch(
            "ai_engine.profiling.persona_updater.update_persona",
            new_callable=AsyncMock,
        ) as mock_llm:

            mock_tracker = mock_tracker_cls.return_value
            mock_tracker.merge.return_value = merged
            mock_llm.return_value = "Updated persona."

            await update_traveler_persona(
                user_id="test_user",
                trip_id="test_trip",
                db=mock_db,
            )

        # Verify merge was called with correct args
        mock_tracker.merge.assert_called_once()
        merge_kwargs = mock_tracker.merge.call_args.kwargs
        assert merge_kwargs["old_counts"] == {
            "budget": {"budget": 1, "moderate": 2, "luxury": 0},
        }
        assert merge_kwargs["profile_data"]["budget_level"] == BudgetLevel.MODERATE

        # Verify merged counts are passed to LLM
        assert mock_llm.call_args.kwargs["preference_counts"] == merged

        # Verify merged counts are persisted
        assert user.preference_counts == merged
