# backend/tests/unit/test_ai_engine/test_chat_handler.py

"""
Integration tests for chat_handler.py phase-aware routing.

Mocks external dependencies (LLM, Redis, parse_intent, trip_graph) to test
the full conversational flow:

    GREETING → SLOT_FILLING → PLAN_GENERATION → ITINERARY_REVIEW → COMPLETED

Tests cover:
    - Greeting with general chat (stays in GREETING)
    - Greeting with plan_trip (transitions to SLOT_FILLING)
    - Greeting with complete info (skips to PLAN_GENERATION)
    - Slot filling with partial info (asks clarifying question)
    - Slot filling with complete info (generates plan)
    - Itinerary review: approve → COMPLETED
    - Itinerary review: modify → re-runs pipeline
    - Itinerary review: question → conversational answer
    - COMPLETED → new trip request (resets and starts over)
    - Session state persistence across multiple turns
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.memory.conversation_state import ConversationPhase, ConversationState


# ── Shared Mock Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_manager():
    """Mock SessionManager that stores state in-memory."""
    storage = {}

    manager = AsyncMock()

    async def fake_resume_or_create(user_id, session_id=None):
        if session_id and session_id in storage:
            return storage[session_id]
        if user_id in storage:
            return storage[user_id]
        state = ConversationState(user_id=user_id)
        storage[user_id] = state
        return state

    async def fake_save(state):
        storage[state.user_id] = state
        return True

    manager.resume_or_create = fake_resume_or_create
    manager.save = fake_save
    return manager


@pytest.fixture
def mock_llm():
    """Mock LLM that returns a canned response."""
    llm = MagicMock()
    response = MagicMock()
    response.content = "Where would you like to travel?"
    llm.invoke.return_value = response
    return llm


@pytest.fixture
def mock_trip_graph():
    """Mock LangGraph trip_graph that returns a mock itinerary."""
    graph = AsyncMock()
    result = {
        "optimized_itinerary": {
            "days": [
                {
                    "day_number": 1,
                    "stops": [
                        {"name": "Pyramids of Giza", "start_time": "09:00"},
                        {"name": "Egyptian Museum", "start_time": "14:00"},
                    ],
                }
            ]
        }
    }
    graph.ainvoke.return_value = result
    return graph


def _make_intent(intent_type, **kwargs):
    """Build a mock intent dict."""
    base = {
        "intent_type": intent_type,
        "destination_city": None,
        "destination_country": None,
        "duration_days": None,
        "travel_dates": None,
        "group_size": None,
        "special_requests": None,
        "missing_fields": [],
    }
    base.update(kwargs)
    return base


# ── GREETING Phase Tests ──────────────────────────────────────────────────────

class TestGreetingPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_greeting_general_chat_stays_in_greeting(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """User says 'Hello' → general_chat → stays in GREETING."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Hi! I'm TourMate. Ready to plan a trip?"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat
        result = await handle_chat("user1", "Hello!")

        assert result["response_type"] == "chat"
        assert "session_id" in result
        assert result["phase"] == "greeting"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_greeting_plan_trip_transitions_to_slot_filling(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """User says 'Plan me a trip' → needs_clarification → SLOT_FILLING."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent(
            "needs_clarification",
            missing_fields=["destination", "duration"],
        )

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Where would you like to go?"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat
        result = await handle_chat("user1", "Plan me a trip")

        assert result["response_type"] == "clarification"
        assert result["phase"] == "slot_filling"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.chat_handler.load_mock_profile")
    async def test_greeting_complete_info_skips_to_plan_generation(
        self, mock_profile, mock_graph, mock_parse, mock_get_manager, mock_manager
    ):
        """User gives full info in first message → skips to PLAN_GENERATION."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent(
            "plan_trip",
            destination_city="Paris",
            destination_country="France",
            duration_days=5,
        )
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }

        from ai_engine.chat.chat_handler import handle_chat
        result = await handle_chat("user1", "Plan me a 5-day trip to Paris")

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None
        # Phase should be ITINERARY_REVIEW (set by set_itinerary in Step 5)
        assert result["phase"] == "itinerary_review"


# ── SLOT_FILLING Phase Tests ─────────────────────────────────────────────────

class TestSlotFillingPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_slot_filling_partial_info_asks_clarification(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """User gives destination only → still missing duration → asks clarification."""
        mock_get_manager.return_value = mock_manager

        # First turn: greeting → slot_filling
        mock_parse.return_value = _make_intent(
            "needs_clarification",
            destination_city="Cairo",
            missing_fields=["duration"],
        )
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "How many days?"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat
        result1 = await handle_chat("user1", "I want to visit Cairo")
        assert result1["phase"] == "slot_filling"

        # Second turn: still in slot_filling, gives duration
        mock_parse.return_value = _make_intent(
            "plan_trip",
            duration_days=3,
        )

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }
        with patch("ai_engine.chat.chat_handler.trip_graph", mock_graph), \
             patch("ai_engine.chat.chat_handler.load_mock_profile", return_value={"user_id": "user1"}):
            result2 = await handle_chat("user1", "3 days")

        assert result2["response_type"] == "itinerary"
        assert result2["phase"] == "itinerary_review"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_slot_filling_general_chat_stays_in_slot_filling(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """User asks a travel question during slot filling → general chat, stays in slot_filling."""
        mock_get_manager.return_value = mock_manager

        # First turn: greeting → slot_filling
        mock_parse.return_value = _make_intent(
            "needs_clarification",
            destination_city="Paris",
            missing_fields=["duration"],
        )
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "How many days?"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat
        await handle_chat("user1", "I want to visit Paris")

        # Second turn: general question
        mock_parse.return_value = _make_intent("general_chat")
        mock_response.content = "Paris is beautiful in spring!"
        result = await handle_chat("user1", "Is Paris safe?")

        assert result["response_type"] == "chat"
        assert result["phase"] == "slot_filling"  # shouldn't change


# ── ITINERARY_REVIEW Phase Tests ──────────────────────────────────────────────

class TestItineraryReviewPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.chat_handler.load_mock_profile")
    async def test_review_approve_transitions_to_completed(
        self, mock_profile, mock_graph, mock_parse, mock_get_manager, mock_manager
    ):
        """User approves itinerary → transitions to COMPLETED."""
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }

        from ai_engine.chat.chat_handler import handle_chat

        # Generate itinerary first
        mock_parse.return_value = _make_intent(
            "plan_trip",
            destination_city="Paris",
            duration_days=3,
        )
        result1 = await handle_chat("user1", "Plan me a 3-day trip to Paris")
        assert result1["phase"] == "itinerary_review"

        # Approve
        mock_parse.return_value = _make_intent("general_chat")
        result2 = await handle_chat("user1", "Looks good, approve!")

        assert result2["response_type"] == "chat"
        assert result2["phase"] == "completed"
        assert "amazing trip" in result2["message"].lower()

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.chat_handler.load_mock_profile")
    async def test_review_question_stays_in_review(
        self, mock_profile, mock_graph, mock_parse, mock_get_manager, mock_manager
    ):
        """User asks a question about itinerary → stays in ITINERARY_REVIEW."""
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }

        from ai_engine.chat.chat_handler import handle_chat

        # Generate itinerary
        mock_parse.return_value = _make_intent(
            "plan_trip",
            destination_city="Paris",
            duration_days=3,
        )
        await handle_chat("user1", "Plan me a 3-day trip to Paris")

        # Ask a question
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Day 1 includes the Pyramids of Giza."
        mock_llm.invoke.return_value = mock_response
        with patch("ai_engine.chat.chat_handler.get_fast_llm", return_value=mock_llm):
            result = await handle_chat("user1", "What's on Day 1?")

        assert result["response_type"] == "chat"
        assert result["phase"] == "itinerary_review"  # stays in review

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.chat_handler.load_mock_profile")
    async def test_review_modify_re_runs_pipeline(
        self, mock_profile, mock_graph, mock_parse, mock_get_manager, mock_manager
    ):
        """User requests modification → re-runs pipeline, stays in review."""
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }

        from ai_engine.chat.chat_handler import handle_chat

        # Generate itinerary
        mock_parse.return_value = _make_intent(
            "plan_trip",
            destination_city="Paris",
            duration_days=3,
        )
        await handle_chat("user1", "Plan me a 3-day trip to Paris")

        # Request modification
        mock_parse.return_value = _make_intent("general_chat")
        result = await handle_chat("user1", "Change the hotel to something cheaper")

        assert result["response_type"] == "itinerary"
        assert result["phase"] == "itinerary_review"  # back to review


# ── COMPLETED Phase Tests ─────────────────────────────────────────────────────

class TestCompletedPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.chat_handler.load_mock_profile")
    async def test_completed_new_trip_resets_and_starts_over(
        self, mock_profile, mock_graph, mock_parse, mock_get_manager, mock_manager
    ):
        """User approves then starts new trip → resets slots, begins new flow."""
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }

        from ai_engine.chat.chat_handler import handle_chat

        # Complete first trip
        mock_parse.return_value = _make_intent(
            "plan_trip",
            destination_city="Paris",
            duration_days=3,
        )
        await handle_chat("user1", "Plan me a 3-day trip to Paris")
        mock_parse.return_value = _make_intent("general_chat")
        await handle_chat("user1", "Looks good, approve!")

        # Start new trip
        mock_parse.return_value = _make_intent(
            "needs_clarification",
            destination_city="Tokyo",
            missing_fields=["duration"],
        )
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "How many days for Tokyo?"
        mock_llm.invoke.return_value = mock_response
        with patch("ai_engine.chat.chat_handler.get_fast_llm", return_value=mock_llm):
            result = await handle_chat("user1", "I want to go to Tokyo next")

        assert result["phase"] == "slot_filling"
        # Verify slots were reset (Tokyo is set, duration is missing)
        manager = await mock_get_manager()
        state = await manager.resume_or_create("user1")
        assert state.slots.destination_city == "Tokyo"
        assert state.slots.duration_days is None


# ── Session Persistence Tests ─────────────────────────────────────────────────

class TestSessionPersistence:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_session_id_returned_in_response(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Every response includes session_id for client tracking."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Hello!"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat
        result = await handle_chat("user1", "Hi")

        assert "session_id" in result
        assert isinstance(result["session_id"], str)
        assert len(result["session_id"]) > 0

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_history_grows_across_turns(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Conversation history accumulates across multiple turns."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Nice weather!"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat

        await handle_chat("user1", "Hi")
        await handle_chat("user1", "How are you?")
        await handle_chat("user1", "What's the weather?")

        manager = await mock_get_manager()
        state = await manager.resume_or_create("user1")
        # 3 user messages + 3 assistant messages = 6 total
        assert len(state.history) == 6
        assert state.turn_count == 3


# ── Streaming Handler Tests ───────────────────────────────────────────────────

class TestHandleChatStream:
    """Tests for the handle_chat_stream async generator."""

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_general_chat_yields_session_text_done(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """General chat stream yields session → text chunks → done."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Hello there!"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        chunks = []
        async for chunk in handle_chat_stream("user1", "Hi"):
            chunks.append(chunk)

        # Should have: session + 2 text chunks ("Hello" + "there!") + done
        types = [c["type"] for c in chunks]
        assert types[0] == "session"
        assert types[-1] == "done"
        assert "text" in types
        assert "done" in types

        # Session chunk should have session_id and phase
        session_chunk = chunks[0]
        assert "session_id" in session_chunk["data"]
        assert "phase" in session_chunk["data"]

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_text_chunks_are_word_by_word(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Text chunks yield one word at a time with trailing space."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Paris is beautiful"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        text_chunks = []
        async for chunk in handle_chat_stream("user1", "Tell me about Paris"):
            if chunk["type"] == "text":
                text_chunks.append(chunk)

        assert len(text_chunks) == 3  # "Paris", "is", "beautiful"
        assert text_chunks[0]["content"] == "Paris "
        assert text_chunks[1]["content"] == "is "
        assert text_chunks[2]["content"] == "beautiful "

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.chat_handler.load_mock_profile")
    async def test_stream_plan_trip_yields_actions_chunk(
        self, mock_profile, mock_graph, mock_parse, mock_get_manager, mock_manager
    ):
        """Plan trip stream yields session → text → actions → done."""
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {"days": [{"day_number": 1, "stops": []}]}
        }
        mock_parse.return_value = _make_intent(
            "plan_trip",
            destination_city="Paris",
            duration_days=3,
        )

        from ai_engine.chat.chat_handler import handle_chat_stream

        chunks = []
        async for chunk in handle_chat_stream("user1", "Plan me a 3-day trip to Paris"):
            chunks.append(chunk)

        types = [c["type"] for c in chunks]
        assert types[0] == "session"
        assert "text" in types
        assert "actions" in types
        assert types[-1] == "done"

        # Actions chunk should contain CREATE_TRIP
        actions_chunk = next(c for c in chunks if c["type"] == "actions")
        assert len(actions_chunk["data"]) == 1
        assert actions_chunk["data"][0]["type"] == "CREATE_TRIP"
        assert "days" in actions_chunk["data"][0]["data"]

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_always_ends_with_done(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Every stream must end with a done chunk."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "OK"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        chunks = []
        async for chunk in handle_chat_stream("user1", "Hi"):
            chunks.append(chunk)

        assert chunks[-1] == {"type": "done", "data": None}

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_session_chunk_comes_first(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Session metadata is always the first chunk yielded."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "OK"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        chunks = []
        async for chunk in handle_chat_stream("user1", "Hi"):
            chunks.append(chunk)

        assert chunks[0]["type"] == "session"
        assert isinstance(chunks[0]["data"]["session_id"], str)
        assert chunks[0]["data"]["phase"] == "greeting"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_clarification_yields_text_no_actions(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Clarification stream yields text but no actions chunk."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent(
            "needs_clarification",
            missing_fields=["destination", "duration"],
        )
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Where would you like to go?"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        chunks = []
        async for chunk in handle_chat_stream("user1", "Plan me a trip"):
            chunks.append(chunk)

        types = [c["type"] for c in chunks]
        assert "session" in types
        assert "text" in types
        assert "actions" not in types  # no itinerary yet
        assert types[-1] == "done"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_saves_session_state(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Stream persists assistant response to session history."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Hello there!"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        async for _ in handle_chat_stream("user1", "Hi"):
            pass  # consume entire stream

        manager = await mock_get_manager()
        state = await manager.resume_or_create("user1")
        # 1 user message + 1 assistant message
        assert len(state.history) == 2
        assert state.history[0].role == "user"
        assert state.history[1].role == "assistant"
        assert state.turn_count == 1

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_empty_message_uses_fallback(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Empty/whitespace message uses 'I uploaded an image' fallback."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "I see you uploaded an image!"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        # Empty string
        chunks_empty = []
        async for chunk in handle_chat_stream("user1", ""):
            chunks_empty.append(chunk)

        # Verify session and done chunks present
        types = [c["type"] for c in chunks_empty]
        assert types[0] == "session"
        assert types[-1] == "done"
        assert "text" in types

        # parse_intent should have been called with the fallback message
        call_args = mock_parse.call_args[0][0]
        assert "image" in call_args.lower()

        # Whitespace-only
        mock_parse.reset_mock()
        chunks_ws = []
        async for chunk in handle_chat_stream("user1", "   "):
            chunks_ws.append(chunk)

        call_args = mock_parse.call_args[0][0]
        assert "image" in call_args.lower()

    @pytest.mark.asyncio
    @patch("ai_engine.chat.chat_handler.get_session_manager")
    @patch("ai_engine.chat.chat_handler.parse_intent")
    @patch("ai_engine.chat.chat_handler.get_fast_llm")
    async def test_stream_multi_turn_carries_session_state(
        self, mock_llm_fn, mock_parse, mock_get_manager, mock_manager
    ):
        """Session state carries across multiple streaming calls."""
        mock_get_manager.return_value = mock_manager
        mock_parse.return_value = _make_intent("general_chat")
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Nice!"
        mock_llm.invoke.return_value = mock_response
        mock_llm_fn.return_value = mock_llm

        from ai_engine.chat.chat_handler import handle_chat_stream

        # Turn 1: greeting
        chunks1 = []
        async for chunk in handle_chat_stream("user1", "Hello!"):
            chunks1.append(chunk)
        session_id_1 = chunks1[0]["data"]["session_id"]
        phase_1 = chunks1[0]["data"]["phase"]

        # Turn 2: slot filling
        mock_parse.return_value = _make_intent(
            "needs_clarification",
            destination_city="Paris",
            missing_fields=["duration"],
        )
        chunks2 = []
        async for chunk in handle_chat_stream("user1", "I want to visit Paris"):
            chunks2.append(chunk)
        session_id_2 = chunks2[0]["data"]["session_id"]
        phase_2 = chunks2[0]["data"]["phase"]

        # Turn 3: more info
        mock_parse.return_value = _make_intent("general_chat")
        chunks3 = []
        async for chunk in handle_chat_stream("user1", "Is it safe?"):
            chunks3.append(chunk)
        session_id_3 = chunks3[0]["data"]["session_id"]
        phase_3 = chunks3[0]["data"]["phase"]

        # All turns share the same session_id
        assert session_id_1 == session_id_2 == session_id_3

        # Session chunk shows phase BEFORE routing, so:
        # Turn 1: greeting (no transition for general_chat)
        # Turn 2: greeting (transition to slot_filling happens DURING this turn)
        # Turn 3: slot_filling (loaded after turn 2 saved it)
        assert phase_1 == "greeting"
        assert phase_2 == "greeting"  # session chunk yielded before routing
        assert phase_3 == "slot_filling"

        # History accumulated across all 3 turns
        manager = await mock_get_manager()
        state = await manager.resume_or_create("user1")
        assert state.turn_count == 3
        assert len(state.history) == 6  # 3 user + 3 assistant

        # Destination was collected and persists
        assert state.slots.destination_city == "Paris"
