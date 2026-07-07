"""
End-to-end test: Full flow — plan → approve → flight select → hotel select.

Simulates a multi-turn conversation via ``handle_chat()`` that exercises the
complete user journey:
  1. Slot filling (interests, preferences)
  2. Itinerary generation (planning → optimization → validation)
  3. Itinerary review → approval
  4. Flight search & selection
  5. Hotel search & selection
  6. Completion

External services (Amadeus flight search, DB hotel search) are mocked so the
test is deterministic and doesn't require network access or a seeded database.
"""

import pytest
import uuid

from unittest.mock import patch, AsyncMock


# ── Mock Data ──────────────────────────────────────────────────────────────────

MOCK_FLIGHT_OFFERS = [
    {
        "offer_index": 0,
        "airline_code": "EK",
        "airline_name": "Emirates",
        "flight_number": "EK123",
        "origin_iata": "DXB",
        "destination_iata": "CAI",
        "departure_at": "2026-07-21T08:00:00",
        "arrival_at": "2026-07-21T10:00:00",
        "departure_at_formatted": "Jul 21, 08:00",
        "arrival_at_formatted": "Jul 21, 10:00",
        "cabin_class": "ECONOMY",
        "total_price": 180.50,
        "currency": "EUR",
        "price_per_adult": "180.50",
        "stops": 0,
        "duration": "PT2H",
        "return_segments": [],
        "raw_offer": {"id": "1", "type": "flight-offer", "source": "GDS"},
    },
    {
        "offer_index": 1,
        "airline_code": "SV",
        "airline_name": "Saudi Arabian Airlines",
        "flight_number": "SV555",
        "origin_iata": "DXB",
        "destination_iata": "CAI",
        "departure_at": "2026-07-21T18:15:00",
        "arrival_at": "2026-07-21T23:15:00",
        "departure_at_formatted": "Jul 21, 18:15",
        "arrival_at_formatted": "Jul 21, 23:15",
        "cabin_class": "ECONOMY",
        "total_price": 228.71,
        "currency": "EUR",
        "price_per_adult": "228.71",
        "stops": 0,
        "duration": "PT5H",
        "return_segments": [],
        "raw_offer": {"id": "2", "type": "flight-offer", "source": "GDS"},
    },
]

MOCK_HOTEL_OFFERS = [
    {
        "id": "hotel_001",
        "name": "Steigenberger Tahrir",
        "category": "hotel",
        "sub_category": "hotel",
        "accommodation_type": "hotel",
        "lat": 30.0429,
        "lon": 31.2347,
        "rating": 4.3,
        "nightly_rate": 120.0,
        "amenities": ["wifi", "pool", "gym"],
        "address": "Cairo Downtown",
        "photos": [],
        "star_class": 4,
    },
    {
        "id": "hotel_002",
        "name": "Marriott Mena House",
        "category": "hotel",
        "sub_category": "resort",
        "accommodation_type": "resort",
        "lat": 29.9758,
        "lon": 31.1334,
        "rating": 4.6,
        "nightly_rate": 250.0,
        "amenities": ["wifi", "pool", "spa", "restaurant"],
        "address": "Pyramids Area, Giza",
        "photos": [],
        "star_class": 5,
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Full-Flow E2E Test
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullFlowE2E:
    """Simulate the complete user journey: plan → approve → flight → hotel → done."""

    @pytest.mark.asyncio
    async def test_full_flow_plan_approve_flight_hotel(self):
        """
        Full flow smoke test:

        1. Plan a 3-day Cairo trip (with interests)
        2. Approve the itinerary
        3. Search and select a flight (Dubai → Cairo)
        4. See hotel options
        5. Select a hotel
        6. Verify COMPLETED phase
        """
        # ── Patch external services ──────────────────────────────────────
        with (
            patch(
                "ai_engine.agents.flight_selection_agent.search_flights_for_trip",
                new=AsyncMock(return_value=MOCK_FLIGHT_OFFERS),
            ),
            patch(
                "ai_engine.agents.hotel_selection_agent.search_hotels_for_trip",
                new=AsyncMock(return_value=MOCK_HOTEL_OFFERS),
            ),
        ):
            # ── Import handle_chat after patching ────────────────────────
            from ai_engine.conversation.orchestrator import handle_chat
            from ai_engine.conversation.redis_memory import get_session_manager

            user_id = f"e2e_full_flow_{uuid.uuid4().hex[:8]}"
            session_id = None

            # ── Track state across turns ─────────────────────────────────
            itinerary_generated = False
            flight_seen = False
            hotel_seen = False
            completed = False
            last_turn_phase = None

            # ── Turn 1: Start planning ───────────────────────────────────
            result = await handle_chat(
                user_id=user_id,
                user_message="plan a 3-day trip to cairo",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            # Should ask for interests / preferences
            print(f"  Turn 1 phase={result.get('phase')} response_type={result.get('response_type')}")

            # ── Turn 2: Provide interests ────────────────────────────────
            result = await handle_chat(
                user_id=user_id,
                user_message="nightlife, culture",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            itinerary = result.get("itinerary")
            if itinerary:
                itinerary_generated = True
                print(f"  Turn 2: itinerary generated with {len(itinerary.get('days', []))} days")
            print(f"  Turn 2 phase={result.get('phase')} response_type={result.get('response_type')}")

            # Verify we eventually get an itinerary
            # (may need a few clarification turns for budget, pace, etc.)
            max_turns = 10
            for turn in range(3, max_turns + 1):
                if not itinerary_generated:
                    # The system may ask clarifying questions — just answer
                    phase = result.get("phase", "")
                    response_type = result.get("response_type", "")
                    msg = result.get("message", "")

                    if phase == "slot_filling" and response_type == "clarification":
                        # Answer with generic preference
                        answer = "moderate budget, cultural"
                        result = await handle_chat(
                            user_id=user_id,
                            user_message=answer,
                            session_id=session_id,
                        )
                        session_id = result.get("session_id", session_id)
                        last_turn_phase = result.get("phase", "")
                        itinerary = result.get("itinerary")
                        if itinerary:
                            itinerary_generated = True
                            print(f"  Turn {turn}: itinerary generated!")
                    elif phase == "itinerary_review":
                        itinerary_generated = True
                        print(f"  Turn {turn}: in itinerary_review (has itinerary)")
                        break
                    else:
                        # Any other response — continue
                        print(f"  Turn {turn}: phase={phase} type={response_type}")
                        result = await handle_chat(
                            user_id=user_id,
                            user_message="moderate",
                            session_id=session_id,
                        )
                        session_id = result.get("session_id", session_id)
                        last_turn_phase = result.get("phase", "")
                else:
                    break

            # We should now be in itinerary_review with an itinerary
            assert itinerary_generated, "Itinerary should have been generated"

            # Verify phase is itinerary_review
            print(f"  Current phase={last_turn_phase}")

            # ── Turn N: Approve the itinerary ────────────────────────────
            # This transitions to FLIGHT_SELECTION
            result = await handle_chat(
                user_id=user_id,
                user_message="looks good",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            print(f"  After approve: phase={last_turn_phase} response_type={result.get('response_type')}")

            # Verify we're in FLIGHT_SELECTION or the system asked about origin
            # (sometimes the orchestrator asks "where are you flying from?")
            assert last_turn_phase in (
                "flight_selection", "itinerary_review"
            ), f"Expected flight_selection or itinerary_review, got {last_turn_phase}"

            # ── Turn N+1: Say we're flying from Dubai ────────────────────
            result = await handle_chat(
                user_id=user_id,
                user_message="from dubai",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            print(f"  After origin: phase={last_turn_phase} response_type={result.get('response_type')}")

            # ── Turn N+2: Say departure date ─────────────────────────────
            result = await handle_chat(
                user_id=user_id,
                user_message="on july 21",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            flight_search_results = result.get("flight_search_results")
            if flight_search_results:
                flight_seen = True
            print(f"  After date: phase={last_turn_phase} flight_options_present={flight_seen}")

            # If the system asks for more details (dates, origin), provide them
            for turn in range(11, 15):
                if not flight_seen and last_turn_phase == "flight_selection":
                    phase = result.get("phase", "")
                    response_type = result.get("response_type", "")
                    msg = (result.get("message") or "").lower()

                    if "origin" in msg or "departure" in msg or "fly from" in msg:
                        result = await handle_chat(
                            user_id=user_id,
                            user_message="dubai",
                            session_id=session_id,
                        )
                    elif "date" in msg or "when" in msg or "july" in msg:
                        result = await handle_chat(
                            user_id=user_id,
                            user_message="july 21",
                            session_id=session_id,
                        )
                    else:
                        # Try generic flight search trigger
                        result = await handle_chat(
                            user_id=user_id,
                            user_message="dubai on july 21",
                            session_id=session_id,
                        )

                    session_id = result.get("session_id", session_id)
                    last_turn_phase = result.get("phase", "")
                    flight_search_results = result.get("flight_search_results")
                    if flight_search_results:
                        flight_seen = True
                    print(f"  Turn {turn}: phase={last_turn_phase} flight_seen={flight_seen}")
                else:
                    break

            assert flight_seen or last_turn_phase in ("hotel_selection", "completed"), (
                f"Should have seen flight options or moved to hotels, phase={last_turn_phase}"
            )

            # ── Turn N+3: Select flight (by number or name) ──────────────
            result = await handle_chat(
                user_id=user_id,
                user_message="select flight 1",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            hotel_suggestions = (
                (result.get("itinerary") or {}).get("accommodation_suggestions", [])
            )
            if hotel_suggestions:
                hotel_seen = True
            print(f"  After select flight: phase={last_turn_phase} hotels_in_response={hotel_seen}")

            # If the system struggled to parse "select flight 1", try by name
            if not hotel_seen and last_turn_phase == "flight_selection":
                result = await handle_chat(
                    user_id=user_id,
                    user_message="I'll take the emirates flight",
                    session_id=session_id,
                )
                session_id = result.get("session_id", session_id)
                last_turn_phase = result.get("phase", "")
                hotel_suggestions = (
                    (result.get("itinerary") or {}).get("accommodation_suggestions", [])
                )
                if hotel_suggestions:
                    hotel_seen = True
                print(f"  After retry select: phase={last_turn_phase} hotels={hotel_seen}")

            # After flight selection, we should be in HOTEL_SELECTION
            # with hotel options shown
            assert last_turn_phase in ("hotel_selection", "booking", "completed", "flight_selection"), (
                f"Expected hotel_selection/booking/completed, got {last_turn_phase}"
            )

            # ── Turn N+4: Select hotel ───────────────────────────────────
            result = await handle_chat(
                user_id=user_id,
                user_message="select hotel 1",
                session_id=session_id,
            )
            session_id = result.get("session_id", session_id)
            last_turn_phase = result.get("phase", "")
            completed = last_turn_phase == "completed"
            print(f"  After select hotel: phase={last_turn_phase} completed={completed}")

            # ── Final assertions ─────────────────────────────────────────
            assert itinerary_generated, "Must have generated an itinerary"
            assert flight_seen, "Should have seen flight options"
            assert hotel_seen, "Should have seen hotel suggestions"
            # Hotel selection transitions to BOOKING (payment confirmation)
            assert last_turn_phase == "booking", (
                f"Expected final phase 'booking', got '{last_turn_phase}'"
            )

            # Log success details
            print()
            print("=" * 60)
            print("Full flow E2E test: ALL PHASES COMPLETED")
            print(f"  Itinerary: generated")
            print(f"  Flight options: shown ({len(MOCK_FLIGHT_OFFERS)} offers)")
            print(f"  Hotel options: shown ({len(MOCK_HOTEL_OFFERS)} hotels)")
            print(f"  Final phase: {last_turn_phase}")
            print("=" * 60)

            # Cleanup
            manager = await get_session_manager()
            await manager.close()
