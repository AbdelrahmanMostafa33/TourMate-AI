"""
End-to-end test: Full AI → Backend flow via WebSocket.

Tests:
1. Server health endpoint
2. WebSocket chat streaming (token-by-token response)
3. GET /api/v1/itinerary/{trip_id} endpoint
4. GET /api/v1/chat/{trip_id}/history endpoint

Run:
    python -m pytest tests/e2e/test_full_flow.py -v --no-header

Requires:
    - Server running on http://localhost:8000
    - Valid Firebase token for WebSocket tests (skipped if not provided)
"""

import os
import json
import asyncio
import pytest
import requests
from unittest.mock import AsyncMock, patch

from ai_engine.chat.unified_router import RouterResult

BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
FIREBASE_TOKEN = os.environ.get("FIREBASE_TEST_TOKEN", "")


# ═════════════════════════════════════════════════════════════════════════════
# 1. Server Health
# ═════════════════════════════════════════════════════════════════════════════


class TestServerHealth:
    """Server is running and endpoints respond."""

    def test_root_endpoint(self):
        """GET / returns 200 with status message."""
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        # Actual response: "TourMate Backend Running"
        assert "Running" in str(data.get("message", "")), f"Got message: {data}"
        print(f"  ✅ Server root: {data['message']}")

    def test_health_endpoint(self):
        """GET /health returns 200."""
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "ok"
        assert data.get("service") == "tourmate-ai"
        print(f"  ✅ Health: status={data['status']}, service={data['service']}")

    def test_api_v1_accessible(self):
        """API v1 endpoints are registered."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        assert resp.status_code == 200, f"Got {resp.status_code}"
        paths = resp.json().get("paths", {})
        assert any("auth" in p for p in paths), "No auth endpoints found"
        assert any("trips" in p for p in paths), "No trips endpoints found"
        assert any("chat" in p for p in paths), "No chat endpoints found"
        print(f"  ✅ API registered {len(paths)} endpoints: {list(paths.keys())[:8]}...")

    def test_schema_valid(self):
        """OpenAPI schema is valid."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        assert resp.status_code == 200
        schema = resp.json()
        assert schema.get("openapi", "").startswith("3.")
        assert "title" in schema.get("info", {})
        print(f"  ✅ OpenAPI: {schema['info']['title']} ({schema['info'].get('version','?')})")

    def test_itinerary_endpoint_registered(self):
        """Itinerary endpoint is in OpenAPI spec."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        paths = resp.json().get("paths", {})
        itinerary_paths = [p for p in paths if "itinerary" in p]
        assert len(itinerary_paths) > 0, (
            f"No /itinerary endpoints found in {list(paths.keys())}"
        )
        print(f"  ✅ Itinerary endpoint registered: {itinerary_paths}")

    def test_all_our_endpoints_registered(self):
        """Verify itinerary + chat + trips endpoints are registered."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        paths = resp.json().get("paths", {})
        expected_prefixes = ["/api/v1/itinerary", "/api/v1/chat", "/api/v1/trips"]
        for prefix in expected_prefixes:
            found = any(p.startswith(prefix) for p in paths)
            assert found, f"Missing endpoint prefix: {prefix}"
            print(f"  ✅ {prefix}* — registered")

    def test_itinerary_404_without_auth(self):
        """Without auth token, endpoint returns 401/403 for protected routes."""
        resp = requests.get(f"{BASE_URL}/api/v1/itinerary/nonexistent", timeout=5)
        assert resp.status_code in (401, 403, 422), (
            f"Expected auth error, got {resp.status_code}: {resp.text[:200]}"
        )
        print(f"  ✅ Auth required for itinerary: got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════════
# 2. Itinerary Endpoint (requires real Firebase token for auth)
# ═════════════════════════════════════════════════════════════════════════════


class TestItineraryEndpoints:
    """GET /api/v1/itinerary/{trip_id} endpoint tests."""

    def test_itinerary_404_without_auth(self):
        """Without auth token, endpoint returns 401/403."""
        resp = requests.get(f"{BASE_URL}/api/v1/itinerary/nonexistent", timeout=5)
        assert resp.status_code in (401, 403, 422), (
            f"Expected auth error, got {resp.status_code}"
        )
        print(f"  ✅ Auth required: got {resp.status_code}")

    @pytest.mark.skipif(not FIREBASE_TOKEN, reason="No FIREBASE_TEST_TOKEN set")
    def test_itinerary_with_token(self):
        """With valid token, endpoint returns 404 (no such trip) or 200."""
        headers = {"Authorization": f"Bearer {FIREBASE_TOKEN}"}
        resp = requests.get(
            f"{BASE_URL}/api/v1/itinerary/nonexistent",
            headers=headers,
            timeout=5,
        )
        # Either 404 (trip not found) or 200 (if trip exists with that ID)
        assert resp.status_code in (404, 200), (
            f"Expected 404 or 200, got {resp.status_code}: {resp.text[:200]}"
        )
        print(f"  ✅ Auth works: got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════════
# 3. WebSocket Chat Endpoint (requires Firebase token)
# ═════════════════════════════════════════════════════════════════════════════


class TestWebSocketChat:
    """
    WebSocket streaming chat test.

    Requires FIREBASE_TEST_TOKEN env var to be set with a valid Firebase
    authentication token.  Skips all tests if not provided.
    """

    @pytest.mark.skipif(not FIREBASE_TOKEN, reason="No FIREBASE_TEST_TOKEN set")
    @pytest.mark.asyncio
    async def test_websocket_health_check_connection(self):
        """Verify WebSocket endpoint accepts connections with valid token."""
        import websockets

        uri = f"{BASE_URL.replace('http://', 'ws://')}/api/v1/ws/chat/new?token={FIREBASE_TOKEN}"

        async with websockets.connect(uri, ping_timeout=5, close_timeout=5) as ws:
            # Send a simple message
            await ws.send(json.dumps({"message": "Hello, I want to plan a trip"}))

            # We should receive events (token, done, etc.)
            response_text = await asyncio.wait_for(ws.recv(), timeout=15)
            response = json.loads(response_text)
            assert "type" in response, f"Expected 'type' in response, got {response_text[:200]}"
            print(f"  ✅ WebSocket connected and received event: {response['type']}")

    @pytest.mark.skipif(not FIREBASE_TOKEN, reason="No FIREBASE_TEST_TOKEN set")
    @pytest.mark.asyncio
    async def test_websocket_streaming_response(self):
        """WebSocket returns token-by-token streaming response."""
        import websockets
        import asyncio

        uri = f"{BASE_URL.replace('http://', 'ws://')}/api/v1/ws/chat/new?token={FIREBASE_TOKEN}"

        async with websockets.connect(uri, ping_timeout=10, close_timeout=10) as ws:
            await ws.send(json.dumps({"message": "Plan me a 2-day trip to Cairo"}))

            # Collect all events
            events = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    events.append(json.loads(msg))
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                pass

            # Verify we got events
            assert len(events) > 0, "No events received from WebSocket"

            event_types = [e.get("type") for e in events]
            print(f"  ✅ Received {len(events)} events: {event_types[:10]}...")

            # Check for expected event types
            has_token = any(t == "token" for t in event_types)
            has_done = any(t == "done" for t in event_types)

            if has_token:
                print(f"  ✅ Token-by-token streaming works!")
            if has_done:
                print(f"  ✅ Stream completed with 'done' event")

            # Check for trip_created (new chat flow)
            has_trip_created = any(t == "trip_created" for t in event_types)
            if has_trip_created:
                trip_event = next(e for e in events if e["type"] == "trip_created")
                print(f"  ✅ Trip created: {trip_event.get('trip_id', 'unknown')}")


# ═════════════════════════════════════════════════════════════════════════════
# 4. AI Pipeline Script (non-HTTP test — uses handle_chat directly)
# ═════════════════════════════════════════════════════════════════════════════


class TestAIPipeline:
    """AI pipeline runs correctly via handle_chat (no WebSocket needed)."""

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    async def test_ai_pipeline_slot_filling_to_itinerary(
        self, mock_get_manager, mock_route, mock_graph
    ):
        """Slot filling → AI pipeline runs → itinerary generated."""
        from ai_engine.chat.conversation_agent import handle_chat
        from ai_engine.memory.conversation_state import ConversationState

        # Setup mock Redis session
        storage = {}
        manager = AsyncMock()
        manager.load.side_effect = lambda sid: storage.get(sid)
        manager.save.side_effect = lambda state: storage.__setitem__(state.session_id, state)
        manager.resume_or_create.side_effect = lambda uid, sid=None: (
            storage.get(sid) if sid and sid in storage else (
                storage.update({f"session_{uid}": ConversationState(user_id=uid)}) or storage[f"session_{uid}"]
            )
        )
        mock_get_manager.return_value = manager
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {
                "destination": "Cairo",
                "duration_days": 2,
                "days": [
                    {
                        "day_number": 1,
                        "theme": "Pyramids & History",
                        "stops": [
                            {
                                "name": "Pyramids of Giza",
                                "category": "attractions",
                                "sub_category": "historic",
                                "lat": 29.9792,
                                "lon": 31.1342,
                                "rating": 4.8,
                                "estimated_duration_minutes": 180,
                                "suggested_time_of_day": "morning",
                                "why_recommended": "Must-see ancient wonder",
                            },
                        ],
                    },
                ],
                "accommodation_suggestions": [],
            }
        }

        # Build mock router that fills all slots in one turn
        mock_route.return_value = RouterResult(
            action="plan_trip",
            response="Generating your itinerary!",
            extracted={
                "destination_city": "Cairo",
                "duration_days": 2,
                "budget_level": "moderate",
                "travel_style": "cultural",
                "pace": "moderate",
                "interests": ["history", "art"],
                "food_preferences": ["local cuisine"],
                "accommodation_preferences": ["boutique hotel"],
            },
        )

        result = await handle_chat(
            user_id="e2e_test_user",
            user_message="Plan me a 2-day cultural trip to Cairo",
        )

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None
        assert len(result["itinerary"]["days"]) == 1
        assert result["itinerary"]["days"][0]["stops"][0]["name"] == "Pyramids of Giza"
        print(f"  ✅ AI pipeline: slot_filling → itinerary generated")
        print(f"  ✅ Itinerary: {len(result['itinerary']['days'])} days, "
              f"{sum(len(d['stops']) for d in result['itinerary']['days'])} stops")


# ═════════════════════════════════════════════════════════════════════════════
# 5. Stream → DB Integration (tests our Phase 4 + 5 changes)
# ═════════════════════════════════════════════════════════════════════════════


class TestStreamToDBFlow:
    """Stream result → create_trip_from_ai_result → stops in DB."""

    @pytest.mark.asyncio
    async def test_stream_result_to_itinerary_stops(self, db_session):
        """Full flow: stream result → trip → ItineraryStop records."""
        from app.services.chat_service import ChatService
        from app.models.itinerary import Itinerary, Day
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from datetime import date

        # Simulate handle_chat_stream 'result' event data
        itinerary_data = {
            "destination": "Cairo",
            "destination_country": "Egypt",
            "start_date": "2026-07-01",
            "end_date": "2026-07-03",
            "number_of_travelers": 2,
            "budget": 1500,
            "accommodation_suggestions": [
                {
                    "name": "Marriott Mena House",
                    "rating": 4.6,
                    "lat": 29.9758,
                    "lon": 31.1334,
                    "why_recommended": "Luxury near pyramids",
                }
            ],
            "days": [
                {
                    "day_number": 1,
                    "theme": "History Day",
                    "stops": [
                        {
                            "name": "Pyramids of Giza",
                            "category": "attractions",
                            "lat": 29.9792,
                            "lon": 31.1342,
                            "rating": 4.8,
                            "estimated_duration_minutes": 180,
                            "suggested_time_of_day": "morning",
                            "why_recommended": "Must-see",
                        },
                        {
                            "name": "Egyptian Museum",
                            "category": "attractions",
                            "lat": 30.0478,
                            "lon": 31.2336,
                            "rating": 4.7,
                            "estimated_duration_minutes": 150,
                            "suggested_time_of_day": "afternoon",
                            "why_recommended": "Artifacts",
                        },
                    ],
                },
            ],
        }

        # This is what process_message_stream() does with the 'result' event
        ai_result = {"itinerary": itinerary_data}

        svc = ChatService(db_session)
        created = await svc.create_trip_from_ai_result(
            user_id="e2e_stream_test",
            ai_result=ai_result,
        )
        await db_session.commit()

        # Verify
        assert created["stops_created"] == 3, (
            f"Expected 3 stops (2 activities + 1 hotel), got {created['stops_created']}"
        )

        itinerary_id = created["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert loaded is not None
        assert len(loaded.days) == 1
        day_stops = sorted(loaded.days[0].stops, key=lambda s: s.order_in_day)
        assert len(day_stops) == 3
        assert day_stops[0].place_snapshot["name"] == "Pyramids of Giza"
        assert day_stops[1].place_snapshot["name"] == "Egyptian Museum"
        assert day_stops[2].place_snapshot["name"] == "Marriott Mena House"
        assert day_stops[2].place_snapshot["category"] == "hotel"

        print(f"  ✅ Stream result → DB: {created['stops_created']} stops created correctly")
