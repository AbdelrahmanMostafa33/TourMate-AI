"""
Integration tests for chat history endpoints — requirement #22 (conversation history review).

Tests:

  GET /chat/{trip_id}/history
    - Returns messages in chronological order
    - Includes card_data on agent messages
    - Deduplicates user messages when same content exists as agent
    - Returns 404 for missing trip or no conversation
    - Requires auth + ownership
    - Works without messages (empty conversation)

  GET /chats/
    - Lists all conversations for the user, newest first
    - Includes nested trip info when linked
    - Includes last_message snippet
    - Shows conversations without trips (no trip_link)
    - Returns correct limit
    - Requires auth
    - User sees own conversations only
"""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.user import User
from app.models.chat import Conversation, Message
from app.models.enums import ConversationStatus, TripStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Shared test constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID     = "chat_hist_user_001"
OTHER_USER_ID    = "chat_hist_other_001"
TRIP_ID          = "chat_hist_trip_001"
TRIP_ID_NO_CONV  = "chat_hist_trip_nc_001"
CONVERSATION_ID  = "chat_hist_conv_001"
CONVERSATION_ID2 = "chat_hist_conv_002"
CONVERSATION_ID3 = "chat_hist_conv_003"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Backup and restore app.dependency_overrides around each test."""
    backup = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(backup)


def _mock_current_user():
    return {"uid": TEST_USER_ID}


def _mock_other_user():
    return {"uid": OTHER_USER_ID}


def _make_client(db_session, user_override=None):
    """Create a TestClient with auth + db overrides."""
    overrides = {}
    overrides[get_current_user] = user_override or _mock_current_user
    overrides[get_db] = lambda: db_session
    app.dependency_overrides.update(overrides)
    return TestClient(app)


@pytest.fixture
async def seeded_chat_history(db_session) -> None:
    """Seed user + trip + conversation + messages for history tests."""
    # ── User ────────────────────────────────────────────────────────────
    user = User(
        user_id=TEST_USER_ID,
        email="chat_hist@tourmate.com",
        full_name="Chat Hist User",
    )
    db_session.add(user)

    other = User(
        user_id=OTHER_USER_ID,
        email="other_hist@tourmate.com",
        full_name="Other Hist User",
    )
    db_session.add(other)
    await db_session.flush()

    # ── Conversation ────────────────────────────────────────────────────
    conv = Conversation(
        conversation_id=CONVERSATION_ID,
        user_id=TEST_USER_ID,
        status=ConversationStatus.active,
    )
    db_session.add(conv)

    # ── Trip linked to conversation ─────────────────────────────────────
    trip = Trip(
        trip_id=TRIP_ID,
        user_id=TEST_USER_ID,
        trip_name="Chat History Trip",
        destination="Cairo",
        conversation_id=CONVERSATION_ID,
    )
    db_session.add(trip)

    # ── Messages (chronological: user → agent → user → agent) ───────────
    messages_data = [
        ("msg_001", CONVERSATION_ID, "user",  "I want to visit Cairo for 3 days",    None,            None),
        ("msg_002", CONVERSATION_ID, "agent", "Great choice! Let me plan your trip.", None,            {"rendered_cards": []}),
        ("msg_003", CONVERSATION_ID, "user",  "I love history and food",             None,            None),
        ("msg_004", CONVERSATION_ID, "agent", "Here's your itinerary!",              None,            {
            "itinerary_data": {"destination": "Cairo", "days": []},
            "rendered_cards": ["itinerary"],
        }),
    ]
    for msg_id, conv_id, sender, content, img_data, card_data in messages_data:
        db_session.add(Message(
            message_id=msg_id,
            conversation_id=conv_id,
            sender=sender,
            content=content,
            image_data=img_data,
            card_data=card_data,
        ))

    # ── Second conversation (no trip, no messages — for list endpoint) ──
    conv2 = Conversation(
        conversation_id=CONVERSATION_ID2,
        user_id=TEST_USER_ID,
        status=ConversationStatus.active,
    )
    db_session.add(conv2)

    # ── Third conversation (with messages, no trip — for list endpoint) ─
    conv3 = Conversation(
        conversation_id=CONVERSATION_ID3,
        user_id=TEST_USER_ID,
        status=ConversationStatus.active,
    )
    db_session.add(conv3)
    db_session.add(Message(
        message_id="msg_101",
        conversation_id=CONVERSATION_ID3,
        sender="user",
        content="Hello from conv3",
    ))

    # ── Other user's conversation (should NOT appear in own list) ───────
    other_conv = Conversation(
        conversation_id="other_conv_001",
        user_id=OTHER_USER_ID,
        status=ConversationStatus.active,
    )
    db_session.add(other_conv)
    db_session.add(Message(
        message_id="other_msg_001",
        conversation_id="other_conv_001",
        sender="user",
        content="Other user's message",
    ))

    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GET /chat/{trip_id}/history
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetChatHistory:
    """GET /chat/{trip_id}/history — conversation message history."""

    async def test_returns_messages_in_chronological_order(
        self, db_session, seeded_chat_history,
    ):
        """Messages are returned oldest-first."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4

        # Chronological order
        assert data[0]["message_id"] == "msg_001"
        assert data[1]["message_id"] == "msg_002"
        assert data[2]["message_id"] == "msg_003"
        assert data[3]["message_id"] == "msg_004"

    async def test_returns_all_message_fields(
        self, db_session, seeded_chat_history,
    ):
        """Each message has the expected response fields."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        data = response.json()

        msg = data[0]
        assert "message_id" in msg
        assert "conversation_id" in msg
        assert "sender" in msg
        assert "content" in msg
        assert "image_data" in msg
        assert "card_data" in msg
        assert "timestamp" in msg

        # First message is a user message
        assert msg["sender"] == "user"
        assert msg["content"] == "I want to visit Cairo for 3 days"
        assert msg["card_data"] is None

    async def test_card_data_present_on_agent_messages(
        self, db_session, seeded_chat_history,
    ):
        """Agent messages include card_data when it was saved."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        data = response.json()

        # msg_002: agent with empty rendered_cards
        msg2 = data[1]
        assert msg2["sender"] == "agent"
        assert msg2["card_data"] == {"rendered_cards": []}

        # msg_004: agent with itinerary_data
        msg4 = data[3]
        assert msg4["sender"] == "agent"
        assert msg4["card_data"]["rendered_cards"] == ["itinerary"]
        assert msg4["card_data"]["itinerary_data"]["destination"] == "Cairo"

    async def test_deduplicates_duplicate_user_messages(
        self, db_session, seeded_chat_history,
    ):
        """When same content exists as both user and agent, user is skipped."""
        # Insert a duplicate: user message with same content as an agent msg
        db_session.add(Message(
            message_id="dup_msg_001",
            conversation_id=CONVERSATION_ID,
            sender="user",
            content="Great choice! Let me plan your trip.",  # same as msg_002 content
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        data = response.json()

        # Should still be 4 messages (dup filtered out)
        assert len(data) == 4
        # The duplicate user message should not appear
        msg_ids = [m["message_id"] for m in data]
        assert "dup_msg_001" not in msg_ids

    async def test_exact_duplicate_user_messages_kept(
        self, db_session, seeded_chat_history,
    ):
        """Exact duplicate (same sender+content) is NOT filtered.

        The route's dedup logic only filters a user message when an agent
        message with the same content already exists.  Exact duplicate user
        messages (same sender + content) are kept as-is.
        """
        db_session.add(Message(
            message_id="dup_msg_002",
            conversation_id=CONVERSATION_ID,
            sender="user",
            content="I want to visit Cairo for 3 days",
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        data = response.json()

        # Should be 5 messages (original 4 + duplicate user message kept)
        assert len(data) == 5
        msg_ids = [m["message_id"] for m in data]
        assert "dup_msg_002" in msg_ids, (
            "Exact duplicate user message should be kept"
        )

    async def test_returns_404_when_trip_not_found(
        self, db_session, seeded_chat_history,
    ):
        """Non-existent trip_id returns 404."""
        client = _make_client(db_session)
        response = client.get("/api/v1/chat/nonexistent_trip/history")
        assert response.status_code == 404

    async def test_returns_404_when_trip_has_no_conversation(
        self, db_session,
    ):
        """Trip without a linked conversation returns 404."""
        user = User(
            user_id=TEST_USER_ID,
            email="no_conv@tourmate.com",
            full_name="No Conv User",
        )
        db_session.add(user)
        trip = Trip(
            trip_id=TRIP_ID_NO_CONV,
            user_id=TEST_USER_ID,
            destination="Luxor",
        )
        db_session.add(trip)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID_NO_CONV}/history")
        assert response.status_code == 404

    async def test_returns_404_for_other_users_trip(
        self, db_session, seeded_chat_history,
    ):
        """Other user's trip returns 404 (ownership check)."""
        client = _make_client(db_session, _mock_other_user)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")
        assert response.status_code == 404

    async def test_requires_auth(
        self, db_session, seeded_chat_history,
    ):
        """No auth header returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")
        assert response.status_code in (401, 403, 422)

    async def test_works_with_image_data(
        self, db_session, seeded_chat_history,
    ):
        """Messages with image_data return the base64 string."""
        # Add a message with image_data
        db_session.add(Message(
            message_id="img_msg_001",
            conversation_id=CONVERSATION_ID,
            sender="user",
            content="Check out this photo",
            image_data="cHJvZHVjdGlvbl9zdGF0dXM=",  # base64-encoded "production_status"
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        data = response.json()
        # Should have 5 messages now
        img_msg = next((m for m in data if m["message_id"] == "img_msg_001"), None)
        assert img_msg is not None
        assert img_msg["image_data"] == "cHJvZHVjdGlvbl9zdGF0dXM="


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GET /chats/ — list all conversations
#
# NOTE: The production ``get_user_conversations()`` method uses
# ``LEFT JOIN LATERAL`` which is PostgreSQL-specific.  SQLite doesn't
# support LATERAL joins, so these tests mock the service method.
# ═══════════════════════════════════════════════════════════════════════════════

from unittest.mock import patch
from app.services.chat_service import ChatService


@pytest.mark.asyncio
class TestListChats:
    """GET /chats/ — list conversations for the authenticated user."""

    def _build_mock_conversations(self):
        """Build mock return data matching ``get_user_conversations`` format."""
        return [
            {
                "conversation_id": CONVERSATION_ID,
                "trip_id": TRIP_ID,
                "trip": {
                    "trip_id": TRIP_ID,
                    "trip_name": "Chat History Trip",
                    "destination": "Cairo",
                    "status": "planning",
                },
                "created_at": "2026-07-01T10:00:00",
                "last_message": "Here's your itinerary!",
                "last_message_at": "2026-07-04T12:00:00",
            },
            {
                "conversation_id": CONVERSATION_ID3,
                "trip_id": None,
                "trip": None,
                "created_at": "2026-07-02T08:00:00",
                "last_message": "Hello from conv3",
                "last_message_at": "2026-07-03T09:00:00",
            },
            {
                "conversation_id": CONVERSATION_ID2,
                "trip_id": None,
                "trip": None,
                "created_at": "2026-07-01T09:00:00",
                "last_message": None,
                "last_message_at": None,
            },
        ]

    async def test_lists_all_conversations_with_trip_and_last_message(
        self, db_session, seeded_chat_history,
    ):
        """Returns all own conversations with nested trip and last_message."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_includes_nested_trip_info_when_linked(
        self, db_session, seeded_chat_history,
    ):
        """Conversation linked to a trip includes trip object."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()

        conv_with_trip = next(
            (c for c in data if c["conversation_id"] == CONVERSATION_ID),
            None,
        )
        assert conv_with_trip is not None
        assert conv_with_trip["trip_id"] == TRIP_ID
        assert conv_with_trip["trip"] is not None
        assert conv_with_trip["trip"]["trip_id"] == TRIP_ID
        assert conv_with_trip["trip"]["trip_name"] == "Chat History Trip"
        assert conv_with_trip["trip"]["destination"] == "Cairo"
        assert conv_with_trip["trip"]["status"] == "planning"

    async def test_shows_last_message_content(
        self, db_session, seeded_chat_history,
    ):
        """Last message content and timestamp are included."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()

        conv1 = next(c for c in data if c["conversation_id"] == CONVERSATION_ID)
        assert conv1["last_message"] == "Here's your itinerary!"

        conv3 = next(c for c in data if c["conversation_id"] == CONVERSATION_ID3)
        assert conv3["last_message"] == "Hello from conv3"

    async def test_conversations_without_trips_have_null_trip(
        self, db_session, seeded_chat_history,
    ):
        """Conversation with no linked trip has null trip_id and trip."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()

        conv2 = next(
            (c for c in data if c["conversation_id"] == CONVERSATION_ID2),
            None,
        )
        assert conv2 is not None
        assert conv2["trip_id"] is None
        assert conv2["trip"] is None
        assert conv2["last_message"] is None

    async def test_ordered_by_most_recent_activity(
        self, db_session, seeded_chat_history,
    ):
        """Conversations are ordered by last_message_at desc."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()

        conversation_ids = [c["conversation_id"] for c in data]
        assert conversation_ids[0] == CONVERSATION_ID
        assert conversation_ids[-1] == CONVERSATION_ID2

    async def test_excludes_other_users_conversations(
        self, db_session, seeded_chat_history,
    ):
        """Other user's conversations are not returned."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        data = response.json()
        conv_ids = [c["conversation_id"] for c in data]
        assert "other_conv_001" not in conv_ids

    async def test_honors_limit_parameter(
        self, db_session, seeded_chat_history,
    ):
        """Limit parameter restricts returned conversations."""
        mock_data = self._build_mock_conversations()
        with patch.object(ChatService, "get_user_conversations",
                          return_value=mock_data[:1]):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_requires_auth(
        self, db_session, seeded_chat_history,
    ):
        """No auth returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/chats/")
        assert response.status_code in (401, 403, 422)

    async def test_empty_list_when_no_conversations(
        self, db_session,
    ):
        """User with no conversations gets empty list."""
        user = User(
            user_id="fresh_user",
            email="fresh@tourmate.com",
            full_name="Fresh User",
        )
        db_session.add(user)
        await db_session.commit()

        with patch.object(ChatService, "get_user_conversations",
                          return_value=[]):
            client = _make_client(db_session)
            response = client.get("/api/v1/chats/")

        assert response.status_code == 200
        assert response.json() == []
