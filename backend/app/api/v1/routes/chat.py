import asyncio
import base64
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import uuid

logger = logging.getLogger(__name__)


class _BoundedSet:
    """A set-like collection with a fixed maximum size.

    When full, adding a new item evicts the item that was added the longest
    time ago (FIFO).  This is used for in-memory caches that should not grow
    unboundedly over the lifetime of the server process.
    """

    def __init__(self, maxsize: int = 10000):
        self._maxsize = maxsize
        self._dict: OrderedDict[str, bool] = OrderedDict()

    def add(self, item: str) -> None:
        """Add an item.  If the set is at capacity, evict the oldest entry."""
        if len(self._dict) >= self._maxsize:
            self._dict.popitem(last=False)
        self._dict[item] = True

    def __contains__(self, item: str) -> bool:
        return item in self._dict

    def __len__(self) -> int:
        return len(self._dict)

    def discard(self, item: str) -> None:
        """Remove an item if present (no-op if absent)."""
        self._dict.pop(item, None)

    def clear(self) -> None:
        """Remove all items."""
        self._dict.clear()


# Track which conversations have already persisted an itinerary card.
# This bounded set limits memory consumption to at most MAX_CONVERSATIONS entries,
# preventing unbounded growth in long-running server processes.
MAX_CONVERSATIONS = 10_000
_conversations_with_itinerary_card: _BoundedSet = _BoundedSet(maxsize=MAX_CONVERSATIONS)

from app.core.database import get_db
from app.core.firebase import verify_token
from app.core.security import get_current_user
from app.models.enums import TripStatus, ItineraryStatus
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.chat import Conversation, Message
from app.models.profile import TripProfile
from app.schemas.chat_protocol import (
    ChatCardType,
    ChatEventType,
    build_event,
    build_history_payload,
    card_segment,
    text_segment,
)
from app.services.chat_service import ChatService
from app.services.image_service import ImageService
from app.ws.manager import manager

router = APIRouter()


def _has_image_signal(image_features: Optional[dict]) -> bool:
    return bool(
        image_features
        and image_features.get("confidence") in ("high", "medium")
        and image_features.get("interests", [])
    )


def _ui_actions(result: dict) -> set[str]:
    ui = result.get("ui") or {}
    actions = ui.get("actions", []) if isinstance(ui, dict) else []
    return {str(action) for action in actions}


def _should_include_itinerary_card(result: dict, include_itinerary: bool) -> bool:
    if not include_itinerary or not result.get("itinerary"):
        return False

    response_type = result.get("response_type")
    # Legacy tests/mocks may not include response_type yet; keep those streams
    # compatible while production responses use response_type for precision.
    if response_type is None:
        return True

    return (
        response_type == "itinerary"
        or "replace_itinerary_card" in _ui_actions(result)
    )


def _itinerary_card_presentation(result: dict, default: str) -> str:
    if "replace_itinerary_card" in _ui_actions(result):
        return "replace"
    return default


def _build_cards_from_ai_result(
    result: dict,
    *,
    include_itinerary: bool,
    itinerary_presentation: str = "append",
) -> tuple[list[dict], dict]:
    """Convert an AI result dict into explicit UI cards + auxiliary metadata."""
    cards: list[dict] = []
    auxiliary: dict = {}

    itinerary = result.get("itinerary")
    phase = result.get("phase")
    if itinerary and _should_include_itinerary_card(result, include_itinerary):
        cards.append({
            "card_type": ChatCardType.ITINERARY.value,
            "data": itinerary,
            "presentation": _itinerary_card_presentation(result, itinerary_presentation),
        })

    accommodation = itinerary.get("accommodation_suggestions", []) if isinstance(itinerary, dict) else []
    should_show_hotels = bool(accommodation) and phase == "hotel_selection"
    if should_show_hotels:
        cards.append({
            "card_type": ChatCardType.HOTEL_OPTIONS.value,
            "data": {
                "options": accommodation,
                "message": None,
                "accommodation_preferences": result.get("accommodation_preferences"),
            },
            "presentation": "append",
        })

    if result.get("booking_data"):
        cards.append({
            "card_type": ChatCardType.BOOKING.value,
            "data": result["booking_data"],
            "presentation": "append",
        })

    if result.get("flight_search_results"):
        cards.append({
            "card_type": ChatCardType.FLIGHT_OPTIONS.value,
            "data": {
                "offers": result["flight_search_results"],
                "message": None,
                "trip_type": result.get("trip_type"),
                "departure_date": result.get("departure_date"),
                "return_date": result.get("return_date"),
                "cabin_class": result.get("cabin_class"),
                "duration_days": result.get("duration_days"),
            },
            "presentation": "append",
        })

    image_features = result.get("image_features")
    if _has_image_signal(image_features):
        cards.append({
            "card_type": ChatCardType.IMAGE_FEATURES.value,
            "data": image_features,
            "presentation": "append",
        })

    if result.get("flight_booking"):
        auxiliary["flight_booking"] = result["flight_booking"]

    return cards, auxiliary


def _response_segments_for_complete(text: str, cards: list[dict]) -> list[dict]:
    segments = []
    if text:
        segments.append(text_segment(text))
    for card in cards:
        segments.append(card_segment(card["card_type"], card["data"]))
    return segments


# ═════════════════════════════════════════════════════════════════════════════
# Helper: نفذ الـ actions على الـ DB
# ═════════════════════════════════════════════════════════════════════════════

async def execute_actions(actions: list, trip: Trip, db: AsyncSession) -> list:
    updated_actions = []

    # Get the first itinerary for this trip (or create one)
    if not trip.itineraries:
        itinerary = Itinerary(
            itinerary_id=str(uuid.uuid4()),
            trip_id=trip.trip_id,
        )
        db.add(itinerary)
        await db.flush()
    else:
        itinerary = trip.itineraries[0]

    for action in actions:
        action_type = action.get("type")
        data        = action.get("data", {})

        # ── ADD_DAY ──────────────────────────────────────────────────────
        if action_type == "ADD_DAY":
            day_number = data.get("day_number", 1)
            all_days   = [d for it in trip.itineraries for d in it.days]
            existing   = next((d for d in all_days if d.day_number == day_number), None)
            if not existing:
                new_day = Day(
                    itinerary_id=itinerary.itinerary_id,
                    day_number=day_number,
                    date=data.get("date"),
                )
                db.add(new_day)
                await db.flush()
                action["generated_id"] = new_day.day_id

        # ── ADD_ACTIVITY ─────────────────────────────────────────────────
        elif action_type == "ADD_ACTIVITY":
            day_number = data.get("day_number", 1)
            all_days   = [d for it in trip.itineraries for d in it.days]
            day        = next((d for d in all_days if d.day_number == day_number), None)
            if not day:
                day = Day(itinerary_id=itinerary.itinerary_id, day_number=day_number)
                db.add(day)
                await db.flush()

            new_stop = ItineraryStop(
                day_id=day.day_id,
                place_snapshot={
                    "name":          data.get("name", ""),
                    "type":          data.get("type", "attraction"),
                    "location_name": data.get("location_name"),
                    "lat":           data.get("lat"),
                    "lon":           data.get("lon"),
                },
                duration_minutes=int(data["duration_hours"] * 60) if data.get("duration_hours") else None,
                order_in_day=data.get("order_in_day", 0),
                ai_notes=data.get("notes"),
            )
            db.add(new_stop)
            await db.flush()
            action["generated_id"] = new_stop.stop_id

        # ── UPDATE_ACTIVITY ──────────────────────────────────────────────
        elif action_type == "UPDATE_ACTIVITY":
            stop_id = data.get("activity_id") or data.get("stop_id")
            if stop_id:
                result = await db.execute(
                    select(ItineraryStop).where(ItineraryStop.stop_id == stop_id)
                )
                stop = result.scalar_one_or_none()
                if stop:
                    if data.get("name") or data.get("notes"):
                        snapshot = stop.place_snapshot or {}
                        if data.get("name"):  snapshot["name"] = data["name"]
                        if data.get("notes"): stop.ai_notes = data["notes"]
                        stop.place_snapshot = snapshot
                    if data.get("duration_hours"):
                        stop.duration_minutes = int(data["duration_hours"] * 60)
                    if data.get("order_in_day") is not None:
                        stop.order_in_day = data["order_in_day"]
                    await db.flush()

        # ── DELETE_ACTIVITY ──────────────────────────────────────────────
        elif action_type == "DELETE_ACTIVITY":
            stop_id = data.get("activity_id") or data.get("stop_id")
            if stop_id:
                await db.execute(
                    delete(ItineraryStop).where(ItineraryStop.stop_id == stop_id)
                )

        # ── UPDATE_TRIP ──────────────────────────────────────────────────
        elif action_type == "UPDATE_TRIP":
            if data.get("destination"):
                trip.destination = data["destination"]
            await db.flush()

        updated_actions.append(action)

    # Touch trip + trip_profile updated_at if any action modified the itinerary
    # سيب onupdate=func.now() في الـ model يشتغل لوحده
    if updated_actions:
        trip.updated_at = None  # trigger onupdate
        # force SQLAlchemy to mark the column as dirty
        from sqlalchemy.sql import func as sqlfunc
        trip.updated_at = sqlfunc.now()

        profile_result = await db.execute(
            select(TripProfile).where(TripProfile.trip_id == trip.trip_id)
        )
        for prof in profile_result.scalars().all():
            prof.updated_at = sqlfunc.now()

    return updated_actions


# ═════════════════════════════════════════════════════════════════════════════
# Helper: تحديث TripProfile من بيانات AI
# ═════════════════════════════════════════════════════════════════════════════

def _update_profile_from_ai(profile: TripProfile, profile_data: dict) -> None:
    """Map AI profile data dict onto a TripProfile ORM object."""
    from app.models.enums import BudgetLevel, TravelStyle, TripPace

    budget_val = profile_data.get("budget_level")
    if budget_val is not None:
        try:
            profile.budget_level = BudgetLevel(budget_val)
        except (ValueError, TypeError):
            pass

    style_val = profile_data.get("travel_style")
    if style_val is not None:
        try:
            profile.travel_style = TravelStyle(style_val)
        except (ValueError, TypeError):
            pass

    pace_val = profile_data.get("pace")
    if pace_val is not None:
        try:
            profile.pace = TripPace(pace_val)
        except (ValueError, TypeError):
            pace_lower = str(pace_val).lower().strip()
            profile.pace = TripPace.MODERATE
            logger.warning(
                "[ChatRoutes] Invalid pace '%s', defaulting to '%s'",
                pace_val, profile.pace.value,
            )

    # List fields
    if profile_data.get("interests"):
        profile.interests = profile_data["interests"]
    if profile_data.get("food_preferences"):
        profile.food_preferences = profile_data["food_preferences"]
    if profile_data.get("accommodation_preferences"):
        profile.accommodation_preferences = profile_data["accommodation_preferences"]


# ═════════════════════════════════════════════════════════════════════════════
# Helper: جيب أو أنشئ Conversation
# ═════════════════════════════════════════════════════════════════════════════

async def get_or_create_conversation(
    trip:    Trip,
    user_id: str,
    db:      AsyncSession,
) -> Conversation:
    """Get or create a conversation for a trip via the Trip.conversation FK."""
    svc          = ChatService(db)
    conversation = await svc.get_or_create_conversation(user_id, trip.trip_id)
    return conversation


# ═════════════════════════════════════════════════════════════════════════════
# Helper: get BehavioralProfile
# ═════════════════════════════════════════════════════════════════════════════

async def get_profile_data(user_id: str, trip_id: str, db: AsyncSession) -> dict:
    """Get trip profile data for the AI pipeline."""
    result  = await db.execute(
        select(TripProfile).where(TripProfile.trip_id == trip_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return {}

    return {
        "budget_level":              profile.budget_level,
        "travel_style":              profile.travel_style,
        "pace":                      profile.pace,
        "interests":                 profile.interests or [],
        "food_preferences":          profile.food_preferences or [],
        "accommodation_preferences": profile.accommodation_preferences or [],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helper: معالجة رسالة واحدة مع تدفق (streaming)
# ═════════════════════════════════════════════════════════════════════════════

async def process_message_stream(
    user_text:    str,
    trip:         Trip,
    conversation: Conversation,
    profile_data: dict,
    ws_key:       str,
    db:           AsyncSession,
    user_id:      str,
    token:        str,
    session_id:   Optional[str] = None,
    image_bytes:  Optional[bytes] = None,
    image_data:   Optional[str] = None,
) -> Optional[str]:
    """Process a message with streaming token-by-token response.

    Uses ``conversation.conversation_id`` as the AI engine's session_id so
    that conversation continuity is maintained across WebSocket reconnects.
    If the Redis ``ConversationState`` has expired (TTL), it is transparently
    rebuilt from DB records (messages, trip, profile).

    Returns the conversation_id (used as session_id) for subsequent calls.
    """
    svc = ChatService(db)

    # ── Use conversation_id as the stable AI engine session_id ────────────
    # This is the key fix for conversation continuity: the AI engine
    # identifies conversation state by session_id.  By using the stable
    # conversation_id (which never changes), we ensure that reopening a
    # conversation always finds (or rebuilds) the correct state.
    effective_session_id = conversation.conversation_id

    logger.info(
        "[DIAG][process_message_stream] ENTRY conv=%s trip=%s user=%s "
        "session_id=%s recovery_state_has=%s state_snapshot_phase=%s",
        conversation.conversation_id, trip.trip_id, user_id,
        session_id, (conversation.state_snapshot is not None),
        conversation.state_snapshot.get("phase") if conversation.state_snapshot else None,
    )

    # ── Ensure Redis has valid ConversationState for this session ──────
    # If the state expired from Redis (TTL), rebuild it from DB records.
    # This must happen BEFORE handle_chat_stream so the AI engine sees
    # the full conversation history on the very first message after reopen.
    try:
        from ai_engine.conversation.redis_memory import get_session_manager
        redis_mgr = await get_session_manager()
        existing = await redis_mgr.load(effective_session_id)
        if existing is None:
            # State not in Redis — rebuild from DB
            rebuilt_dict = await svc.rebuild_conversation_state_from_db(
                conversation.conversation_id, user_id,
            )
            if rebuilt_dict is not None:
                from ai_engine.conversation.conversation_state import ConversationState
                rebuilt_state = ConversationState.from_dict(rebuilt_dict)
                await redis_mgr.save(rebuilt_state)
                logger.info(
                    "[ChatRoutes] Rebuilt Redis ConversationState for session %s "
                    "from DB records (%d msgs, phase=%s)",
                    effective_session_id,
                    len(rebuilt_state.history),
                    rebuilt_state.phase.value,
                )
            else:
                # No DB history yet — will create fresh state in handle_chat_stream
                logger.info(
                    "[ChatRoutes] No DB history to rebuild for session %s — "
                    "will create fresh ConversationState",
                    effective_session_id,
                )
        else:
            # State exists in Redis — extend TTL so it doesn't expire during
            # a long planning conversation.
            await redis_mgr.extend_ttl(effective_session_id)
            logger.debug(
                "[ChatRoutes] Found existing Redis state for session %s "
                "(phase=%s, history=%d msgs)",
                effective_session_id,
                existing.phase.value,
                len(existing.history),
            )
    except Exception as rebuild_err:
        logger.warning(
            "[ChatRoutes] Redis rebuild check failed (non-fatal): %s",
            rebuild_err,
        )

    # ── Save user message (with image if provided) ────────────────────────
    await svc.save_user_message(conversation.conversation_id, user_text, image_data=image_data)
    await db.commit()

    # ── typing ───────────────────────────────────────────────────────────
    await manager.send(ws_key, {"type": "typing"})

    # ── Stream AI response ───────────────────────────────────────────────
    full_response = ""
    actions       = []
    ai_session_id = effective_session_id  # always the conversation_id
    approve_action = None
    profile_from_ai = None
    pool_state_from_ai = None
    image_features_from_result = None
    # Collect canonical segment list for chat history reconstruction.
    # All segments (text + card) that Flutter renders live are also stored
    # here so REST history returns exactly the same data.
    response_segments: list[dict] = []
    response_cards: list[dict] = []
    response_auxiliary: dict = {}

    initial_pool_state = await svc.load_pool_for_trip(trip.trip_id)

    # ── Protocol event sequence counter ───────────────────────────────────
    _seq = 0

    # ── Send RESPONSE_STARTED ────────────────────────────────────────────
    _seq += 1
    await manager.send(ws_key, build_event(
        ChatEventType.RESPONSE_STARTED,
        sequence=_seq,
    ))

    try:
        from ai_engine.conversation.orchestrator import handle_chat_stream

        # If Redis is down or the session expired, recover structured state
        # (phase, slots, turn_count) from the DB state_snapshot column so the
        # user can seamlessly continue their conversation.
        _recovery_state = conversation.state_snapshot

        async for chunk in handle_chat_stream(
            user_id=user_id,
            user_message=user_text,
            image_bytes=image_bytes,
            token=token,
            session_id=effective_session_id,
            initial_pool_state=initial_pool_state,
            recovery_state=_recovery_state,
        ):
            event_type = chunk.get("type")

            if event_type == "session":
                session_data  = chunk.get("data", {})
                ai_session_id = session_data.get("session_id")

            elif event_type == "text":
                content        = chunk.get("content", "")
                full_response += content
                # NEW PROTOCOL: TEXT_DELTA
                _seq += 1
                await manager.send(ws_key, build_event(
                    ChatEventType.TEXT_DELTA,
                    sequence=_seq,
                    data={"text": content},
                ))

            elif event_type == "progress":
                await manager.send(ws_key, chunk)

            elif event_type == "phase":
                await manager.send(ws_key, chunk)

                phase = chunk.get("data", {}).get("phase")
                if phase == "completed":
                    approve_action = {
                        "type": "APPROVE_TRIP",
                    }

            elif event_type == "result":
                result         = chunk.get("data", {})
                result_message = result.get("message", "")
                if result_message:
                    full_response = result_message

                action_type = result.get("action", "create_trip")
                if action_type == "approve_itinerary":
                    result_phase = result.get("phase", "")
                    if result_phase == "completed":
                        approve_action = {"type": "APPROVE_TRIP"}
                    else:
                        approve_action = {"type": "APPROVE_ITINERARY"}

                # ── Build cards from AI result using the shared helper ────
                cards, auxiliary = _build_cards_from_ai_result(
                    result,
                    include_itinerary=True,
                    itinerary_presentation="append",
                )
                response_auxiliary.update(auxiliary)

                # Track globally for persistence at end of stream
                response_cards = cards

                for card in cards:
                    card_type = card["card_type"]
                    card_data = card["data"]
                    presentation = card.get("presentation", "append")

                    # ── NEW PROTOCOL: CARD event ─────────────────────────
                    _seq += 1
                    await manager.send(ws_key, build_event(
                        ChatEventType.CARD,
                        sequence=_seq,
                        data={
                            "card_type": card_type,
                            "data": card_data,
                            "presentation": presentation,
                        },
                    ))

                    # ── Per-card-type logic (legacy sends removed) ────────
                    #    Only the new protocol CARD event above is sent to the
                    #    client.  This section handles side-effects: tracking
                    #    itinerary actions for DB persistence, and diagnostic logs.
                    if card_type == ChatCardType.ITINERARY.value:
                        # Track itinerary action for DB persistence
                        actions = [{"type": "CREATE_TRIP", "data": card_data}]
                        # Remember that this conversation has received its first
                        # itinerary card (used by websocket_chat pre-population).
                        _conversations_with_itinerary_card.add(conversation.conversation_id)
                        logger.info(
                            "[ChatRoutes] Itinerary card via protocol: ws_key=%s dest=%s days=%d stops=%d",
                            ws_key,
                            card_data.get("destination", "?"),
                            len(card_data.get("days", [])),
                            sum(len(d.get("stops", [])) for d in card_data.get("days", [])),
                        )

                    elif card_type == ChatCardType.FLIGHT_OPTIONS.value:
                        offers = card_data.get("offers", [])
                        if offers:
                            logger.info(
                                "[FlightOptions] Sending %d offers via protocol CARD event",
                                len(offers),
                            )

                    elif card_type == ChatCardType.IMAGE_FEATURES.value:
                        logger.info(
                            "[ChatRoutes] Forwarded image_features via protocol card: %s",
                            card_data.get("interests", [])[:3],
                        )

                # ── Capture profile / pool from result ────────────────────
                if result.get("profile"):
                    profile_from_ai = result["profile"]
                if result.get("pool_state"):
                    pool_state_from_ai = result["pool_state"]

                # ── Capture flight_booking for persistence (not a card) ───
                if result.get("flight_booking"):
                    response_auxiliary["flight_booking"] = result["flight_booking"]

                # ── Build canonical segments for persistence ──────────────
                response_segments = _response_segments_for_complete(full_response, cards)

                # Capture image_features_from_result for DB persistence
                image_features_from_result = result.get("image_features")

            elif event_type == "done":
                # Don't forward 'done' yet — wait until persistence completes.
                pass

    except Exception as exc:
        logger.exception("[ChatRoutes] AI engine streaming failed: %s", exc)
        error_response = ChatService.build_error_response()
        full_response  = error_response["message"]
        actions        = []
        ai_session_id  = None
        approve_action = None
        # Send negative event to client in protocol format
        _seq += 1
        await manager.send(ws_key, build_event(
            ChatEventType.TEXT_DELTA,
            sequence=_seq,
            data={"text": full_response},
        ))

    # ── At this point, the stream is consumed. Do persistence, then send ──
    #    completion to the client.
    #    This fixes the race where 'done' arrived before the DB was updated.

    # ── Handle APPROVE_TRIP action ───────────────────────────────────────
    was_approved = False
    if approve_action:
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries)
                .selectinload(Itinerary.days),
                selectinload(Trip.conversation),
                selectinload(Trip.trip_profiles),
            )
            .where(Trip.trip_id == trip.trip_id)
        )
        trip = result.scalar_one()

        from sqlalchemy.sql import func as sqlfunc

        if approve_action["type"] == "APPROVE_TRIP":
            # Final booking approval — mark as awaiting_booking
            trip.status      = TripStatus.awaiting_booking
            trip.approved_at = sqlfunc.now()
            if trip.itineraries:
                for itin in trip.itineraries:
                    itin.status = ItineraryStatus.active
            logger.info(
                "[ChatRoutes] Trip %s fully approved — status=awaiting_booking",
                trip.trip_id,
            )
        elif approve_action["type"] == "APPROVE_ITINERARY":
            # First-time itinerary approval — mark as itinerary_draft
            trip.status      = TripStatus.itinerary_draft
            trip.approved_at = sqlfunc.now()
            logger.info(
                "[ChatRoutes] Trip %s itinerary approved — status=itinerary_draft",
                trip.trip_id,
            )

        # Touch trip_profile updated_at (Cairo via DB)
        if trip.trip_profiles:
            for prof in trip.trip_profiles:
                prof.updated_at = sqlfunc.now()

        # ── Update traveler_persona based on this approved trip ────────
        try:
            from app.services.profile_service import update_traveler_persona
            await update_traveler_persona(
                user_id=user_id,
                trip_id=trip.trip_id,
                db=db,
            )
        except Exception as persona_err:
            logger.warning(
                "[ChatRoutes] Failed to update traveler persona (non-fatal): %s",
                persona_err,
            )

        was_approved = True

    # ── Execute actions ──────────────────────────────────────────────────
    updated_actions = []
    stops_created = 0
    if actions:
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries)
                .selectinload(Itinerary.days)
                .selectinload(Day.stops),
                selectinload(Trip.conversation),
                selectinload(Trip.trip_profiles),
            )
            .where(Trip.trip_id == trip.trip_id)
        )
        trip = result.scalar_one()

        create_action = next((a for a in actions if a.get("type") == "CREATE_TRIP"), None)
        if create_action:
            itinerary_data = create_action.get("data", {})
            days_data = itinerary_data.get("days", [])
            if days_data and trip.itineraries:
                itinerary = trip.itineraries[0]

                # Increment version (updated_at handled by onupdate)
                itinerary.version_number = (itinerary.version_number or 1) + 1

                from app.services.itinerary_service import ItineraryService
                itin_svc = ItineraryService(db)

                for day_obj in itinerary.days:
                    await db.execute(
                        delete(ItineraryStop).where(ItineraryStop.day_id == day_obj.day_id)
                    )
                await db.flush()

                start_date_raw = itinerary_data.get("start_date")
                start_date = None
                if start_date_raw:
                    try:
                        from datetime import date
                        start_date = date.fromisoformat(start_date_raw)
                    except (ValueError, TypeError):
                        pass

                stops_created = await itin_svc.create_stops_from_ai_days(
                    itinerary_id=itinerary.itinerary_id,
                    days_data=days_data,
                    accommodation_suggestions=itinerary_data.get("accommodation_suggestions"),
                    start_date=start_date,
                )
                await db.flush()

                # Touch trip.updated_at + profile.updated_at (Cairo via DB)
                from sqlalchemy.sql import func as sqlfunc
                trip.updated_at = sqlfunc.now()

                if trip.trip_profiles:
                    for prof in trip.trip_profiles:
                        prof.updated_at = sqlfunc.now()

                if pool_state_from_ai:
                    await svc.save_pool_for_trip(trip.trip_id, pool_state_from_ai)

            # ── Persist TripProfile from AI ──────────────────────────────
            if profile_from_ai:
                existing_profile = trip.trip_profiles[0] if trip.trip_profiles else None
                if existing_profile:
                    _update_profile_from_ai(existing_profile, profile_from_ai)
                    from sqlalchemy.sql import func as sqlfunc
                    existing_profile.updated_at = sqlfunc.now()
                else:
                    new_profile = TripProfile(
                        profile_id=str(uuid.uuid4()),
                        trip_id=trip.trip_id,
                    )
                    _update_profile_from_ai(new_profile, profile_from_ai)
                    db.add(new_profile)
                    logger.info(
                        "[ChatRoutes] Created TripProfile %s from AI result for trip %s",
                        new_profile.profile_id, trip.trip_id,
                    )

                if not trip.trip_profiles:
                    trip.trip_profiles = [existing_profile] if existing_profile else [new_profile]

        remaining_actions = [a for a in actions if a.get("type") != "CREATE_TRIP"]
        if remaining_actions:
            updated_actions = await execute_actions(remaining_actions, trip, db)

    if stops_created > 0:
        logger.info(
            "[ChatRoutes] Updated itinerary %s with %d stops from AI result",
            trip.itineraries[0].itinerary_id if trip.itineraries else "?",
            stops_created,
        )

    # ── Save AI response to DB (with canonical segments for history) ──
    if full_response:
        card_data_for_db = build_history_payload(
            text=full_response,
            cards=response_cards,
            auxiliary=response_auxiliary if response_auxiliary else None,
        ) if response_segments else None
        await svc.save_agent_message(
            conversation.conversation_id,
            full_response,
            card_data=card_data_for_db,
        )

    # ── Sync Redis state to DB + persist state snapshot ───────────────────
    if ai_session_id:
        # Retry with exponential backoff: 100ms, 200ms, 400ms
        for attempt in range(1, 4):
            try:
                from ai_engine.conversation.redis_memory import get_session_manager
                redis_manager = await get_session_manager()
                if redis_manager.is_connected:
                    redis_state = await redis_manager.load(ai_session_id)
                    if redis_state:
                        # 1. Sync Redis message history to DB
                        if redis_state.history:
                            redis_msgs = [m.to_dict() for m in redis_state.history]
                            await svc.sync_redis_to_db(conversation.conversation_id, redis_msgs)
                        # 2. Persist lightweight state snapshot on Conversation record
                        #    This ensures the AI can recover structured state (phase, slots,
                        #    turn_count) from PostgreSQL alone if Redis is lost.
                        await svc.save_state_snapshot(
                            conversation.conversation_id,
                            redis_state,
                        )
                    # Success — exit retry loop
                    break
            except Exception as sync_err:
                if attempt < 3:
                    delay = 0.1 * (2 ** (attempt - 1))  # 100ms, 200ms, 400ms
                    logger.warning(
                        "[ChatRoutes] Redis sync attempt %d/3 failed, retrying in %.0fms: %s",
                        attempt, delay * 1000, sync_err,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        "[ChatRoutes] Redis sync failed after 3 attempts (non-fatal): %s",
                        sync_err,
                    )


    # ── Persist image features to DB (non-critical) ──────────────────────
    if image_features_from_result and isinstance(image_features_from_result, dict):
        signal = (
            image_features_from_result.get("confidence") in ("high", "medium")
            and image_features_from_result.get("interests", [])
        )
        if signal:
            try:
                from ai_engine.schemas.vision_schema import VisionFeatures
                img_svc = ImageService(db)
                await img_svc.create_image_with_features(
                    trip_id=trip.trip_id,
                    vision_features=VisionFeatures(**image_features_from_result),
                )
                await db.commit()
            except Exception as img_err:
                logger.warning("[ChatRoutes] Failed to persist image features (non-fatal): %s", img_err)
                await db.rollback()

    await db.commit()

    logger.info(
        "[DIAG][process_message_stream] RETURN conv=%s ai_session_id=%s "
        "was_approved=%s stops_created=%d",
        conversation.conversation_id, ai_session_id,
        was_approved, stops_created,
    )

    # ── Send RESPONSE_COMPLETED (after all persistence is done) ──────────
    _seq += 1
    completed_data = {
        "status": "ok",
        "segments": response_segments,
    }
    await manager.send(ws_key, build_event(
        ChatEventType.RESPONSE_COMPLETED,
        sequence=_seq,
        data=completed_data,
    ))

    # ── Notify Flutter that trip was approved (after commit) ──────────────
    if was_approved:
        _seq += 1
        await manager.send(ws_key, build_event(
            ChatEventType.TRIP_APPROVED,
            sequence=_seq,
        ))

    # ── Notify Flutter of actions ─────────────────────────────────────────
    if updated_actions:
        _seq += 1
        await manager.send(ws_key, build_event(
            ChatEventType.ACTIONS_APPLIED,
            sequence=_seq,
            data={"actions": updated_actions},
        ))
        _seq += 1
        await manager.send(ws_key, build_event(
            ChatEventType.ITINERARY_UPDATED,
            sequence=_seq,
        ))

    return ai_session_id


# ═════════════════════════════════════════════════════════════════════════════
# WS /ws/chat/new?token=xxx
# ═════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws/chat/new")
async def websocket_new_chat(
    websocket: WebSocket,
    token:     str          = Query(...),
    db:        AsyncSession = Depends(get_db),
):
    # ── Auth ─────────────────────────────────────────────────────────────
    user = verify_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    user_id = user["uid"]
    ws_key  = "new_" + user_id

    await manager.connect(ws_key, websocket)

    try:
        trip:             Trip         = None
        conversation:     Conversation = None
        profile_data:     dict         = {}
        history_list:     list         = []
        pending_messages: list         = []
        ai_session_id:    Optional[str] = None

        while True:
            data      = await websocket.receive_json()
            
            # ── Heartbeat ping/pong ────────────────────────────────────────
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            user_text = data.get("message", "").strip()
            
            # Extract image data if present
            image_bytes = None
            image_data = data.get("image")
            if image_data:
                try:
                    image_bytes = base64.b64decode(image_data)
                except Exception as e:
                    logger.warning("[ChatRoutes] Failed to decode image data: %s", e)
            
            if not user_text and not image_bytes:
                continue

            # Use placeholder message for image-only uploads
            effective_message = user_text if user_text else "I uploaded an image for my trip."

            svc = ChatService(db)

            if trip and conversation:
                lock = manager.get_lock(ws_key)
                async with lock:
                    ai_session_id = await process_message_stream(
                        user_text=effective_message,
                        trip=trip,
                        conversation=conversation,
                        profile_data=profile_data,
                        ws_key=ws_key,
                        db=db,
                        user_id=user_id,
                        token=token,
                        session_id=ai_session_id,
                        image_bytes=image_bytes,
                        image_data=image_data,
                    )

                history_list.append({"role": "user", "content": effective_message})
                if len(history_list) > 20:
                    history_list = history_list[-20:]
                continue

            pending_messages.append({
                "role": "user",
                "content": effective_message,
                "image_data": image_data,
            })

            await manager.send(ws_key, {"type": "typing"})

            full_response = ""
            actions       = []
            profile_data_from_ai = None
            pool_state_from_ai = None
            image_features_from_result = None
            # Collect canonical segment list for chat history reconstruction
            response_segments_new: list[dict] = []
            response_cards_new: list[dict] = []
            response_auxiliary_new: dict = {}
            _new_seq = 0

            # ── Send RESPONSE_STARTED ────────────────────────────────────
            _new_seq += 1
            await manager.send(ws_key, build_event(
                ChatEventType.RESPONSE_STARTED,
                sequence=_new_seq,
            ))

            try:
                from ai_engine.conversation.orchestrator import handle_chat_stream

                async for chunk in handle_chat_stream(
                    user_id=user_id,
                    user_message=effective_message,
                    image_bytes=image_bytes,
                    token=token,
                    session_id=ai_session_id,
                ):
                    event_type = chunk.get("type")

                    if event_type == "session":
                        session_data  = chunk.get("data", {})
                        ai_session_id = session_data.get("session_id")

                    elif event_type == "text":
                        content        = chunk.get("content", "")
                        full_response += content
                        _new_seq += 1
                        await manager.send(ws_key, build_event(
                            ChatEventType.TEXT_DELTA,
                            sequence=_new_seq,
                            data={"text": content},
                        ))

                    elif event_type == "progress":
                        await manager.send(ws_key, chunk)

                    elif event_type == "phase":
                        await manager.send(ws_key, chunk)

                    elif event_type == "result":
                        result         = chunk.get("data", {})
                        result_message = result.get("message", "")
                        if result_message:
                            full_response = result_message

                        # ── Build cards from AI result using the shared helper ────
                        cards, auxiliary = _build_cards_from_ai_result(
                            result,
                            include_itinerary=True,
                            itinerary_presentation="append",
                        )
                        response_auxiliary_new.update(auxiliary)

                        # Track globally for persistence
                        response_cards_new = cards

                        for card in cards:
                            card_type = card["card_type"]
                            card_data = card["data"]
                            presentation = card.get("presentation", "append")

                            # ── NEW PROTOCOL: CARD event ─────────────────
                            _new_seq += 1
                            await manager.send(ws_key, build_event(
                                ChatEventType.CARD,
                                sequence=_new_seq,
                                data={
                                    "card_type": card_type,
                                    "data": card_data,
                                    "presentation": presentation,
                                },
                            ))

                            # ── Per-card-type logic (legacy sends removed) ────────
                            #    Only the new protocol CARD event above is sent.
                            #    This section handles side-effects and logs.
                            if card_type == ChatCardType.ITINERARY.value:
                                actions = [{"type": "CREATE_TRIP", "data": card_data}]
                                logger.info(
                                    "[ChatRoutes] Itinerary card via protocol (new chat): "
                                    "ws_key=%s dest=%s days=%d stops=%d",
                                    ws_key,
                                    card_data.get("destination", "?"),
                                    len(card_data.get("days", [])),
                                    sum(len(d.get("stops", [])) for d in card_data.get("days", [])),
                                )

                            elif card_type == ChatCardType.FLIGHT_OPTIONS.value:
                                offers2 = card_data.get("offers", [])
                                if offers2:
                                    logger.info(
                                        "[FlightOptions][new_chat] Sending %d offers via protocol CARD event",
                                        len(offers2),
                                    )

                            elif card_type == ChatCardType.IMAGE_FEATURES.value:
                                logger.info(
                                    "[ChatRoutes] Forwarded image_features via protocol card (new chat): %s",
                                    card_data.get("interests", [])[:3],
                                )

                        # ── Capture profile / pool from result ────────────
                        if result.get("profile"):
                            profile_data_from_ai = result["profile"]
                        if result.get("pool_state"):
                            pool_state_from_ai = result["pool_state"]

                        # ── Capture flight_booking for persistence ────────
                        if result.get("flight_booking"):
                            response_auxiliary_new["flight_booking"] = result["flight_booking"]

                        # ── Build canonical segments for persistence ──────
                        response_segments_new = _response_segments_for_complete(full_response, cards)

                        # Capture image_features_from_result for DB persistence
                        image_features_from_result = result.get("image_features")

                    elif event_type == "done":
                        pass

            except Exception as exc:
                logger.exception("[ChatRoutes] AI engine streaming failed in websocket_new_chat: %s", exc)
                error_response = ChatService.build_error_response()
                full_response  = error_response["message"]
                actions        = []
                _new_seq += 1
                await manager.send(ws_key, build_event(
                    ChatEventType.TEXT_DELTA,
                    sequence=_new_seq,
                    data={"text": full_response},
                ))

            for action in actions:
                if action.get("type") == "CREATE_TRIP" and not trip:
                    ai_result = {"itinerary": action.get("data", {})}
                    if profile_data_from_ai:
                        ai_result["profile"] = profile_data_from_ai
                    if pool_state_from_ai:
                        ai_result["pool_state"] = pool_state_from_ai
                    try:
                        created = await svc.create_trip_from_ai_result(
                            user_id,
                            ai_result,
                        )

                        trip         = created["trip"]
                        conversation = created["conversation"]

                        # Mark this conversation as having an itinerary card
                        # so subsequent process_message_stream calls (follow-ups)
                        # don't render duplicate itinerary cards.
                        if conversation:
                            has_itinerary_card = any(
                                c.get("card_type") == ChatCardType.ITINERARY.value
                                for c in response_cards_new
                            )
                            if has_itinerary_card:
                                _conversations_with_itinerary_card.add(conversation.conversation_id)

                        for msg in pending_messages:
                            await svc.save_message(
                                conversation_id=conversation.conversation_id,
                                sender="user" if msg["role"] == "user" else "agent",
                                content=msg["content"],
                                image_data=msg.get("image_data"),
                            )
                        pending_messages = []

                        # ── Persist image features if available ──────────────
                        if image_features_from_result and isinstance(image_features_from_result, dict):
                            signal = (
                                image_features_from_result.get("confidence") in ("high", "medium")
                                and image_features_from_result.get("interests", [])
                            )
                            if signal:
                                try:
                                    from ai_engine.schemas.vision_schema import VisionFeatures
                                    img_svc = ImageService(db)
                                    await img_svc.create_image_with_features(
                                        trip_id=trip.trip_id,
                                        vision_features=VisionFeatures(**image_features_from_result),
                                    )
                                except Exception as img_err:
                                    logger.warning(
                                        "[ChatRoutes] Failed to persist image features (non-fatal): %s",
                                        img_err,
                                    )

                        # ── Persist state snapshot right after trip creation ───────
                        #    This captures the initial phase/slots from the AI
                        #    engine before any follow-up messages are processed.
                        if ai_session_id:
                            try:
                                from ai_engine.conversation.redis_memory import get_session_manager
                                _rm = await get_session_manager()
                                if _rm.is_connected:
                                    _redis_state = await _rm.load(ai_session_id)
                                    if _redis_state:
                                        await svc.save_state_snapshot(
                                            conversation.conversation_id,
                                            _redis_state,
                                        )
                            except Exception as snap_err:
                                logger.warning(
                                    "[ChatRoutes] Failed to save initial state snapshot (non-fatal): %s",
                                    snap_err,
                                )

                        await db.commit()

                        _new_seq += 1
                        await manager.send(ws_key, build_event(
                            ChatEventType.TRIP_CREATED,
                            sequence=_new_seq,
                            data={
                                "trip_id": trip.trip_id,
                                "itinerary_id": created["itinerary"].itinerary_id,
                            },
                        ))

                        profile_data = await get_profile_data(user_id, trip.trip_id, db)

                        manager.disconnect(ws_key)
                        ws_key = trip.trip_id
                        await manager.connect_existing(ws_key, websocket)

                    except Exception as create_exc:
                        logger.exception(
                            "[ChatRoutes] Failed to create trip from AI result: %s",
                            create_exc,
                        )
                        await db.rollback()
                        await manager.send(ws_key, {
                            "type": "error",
                            "data": "Failed to save trip. Please try again.",
                        })

                    break

            non_create_actions = [a for a in actions if a.get("type") != "CREATE_TRIP"]
            updated_actions    = []

            if trip and non_create_actions:
                updated_actions = await execute_actions(non_create_actions, trip, db)
                await db.commit()

            pending_messages.append({"role": "assistant", "content": full_response})

            if conversation and full_response:
                card_data_for_db = build_history_payload(
                    text=full_response,
                    cards=response_cards_new,
                    auxiliary=response_auxiliary_new if response_auxiliary_new else None,
                ) if response_segments_new else None
                await svc.save_agent_message(
                    conversation.conversation_id,
                    full_response,
                    card_data=card_data_for_db,
                )
                await db.commit()

            if updated_actions:
                _new_seq += 1
                await manager.send(ws_key, build_event(
                    ChatEventType.ACTIONS_APPLIED,
                    sequence=_new_seq,
                    data={"actions": updated_actions},
                ))
                _new_seq += 1
                await manager.send(ws_key, build_event(
                    ChatEventType.ITINERARY_UPDATED,
                    sequence=_new_seq,
                ))

            # ── Send RESPONSE_COMPLETED ──────────────────────────────────
            _new_seq += 1
            await manager.send(ws_key, build_event(
                ChatEventType.RESPONSE_COMPLETED,
                sequence=_new_seq,
                data={
                    "status": "ok",
                    "segments": response_segments_new,
                },
            ))

            history_list.append({"role": "user",      "content": effective_message})
            history_list.append({"role": "assistant", "content": full_response})
            if len(history_list) > 20:
                history_list = history_list[-20:]

    except WebSocketDisconnect:
        manager.disconnect(ws_key)
    except Exception as exc:
        # Catch any unexpected runtime error (e.g. Starlette "WebSocket is not
        # connected. Need to call 'accept' first.") that would otherwise
        # propagate as an ASGI exception and crash the server process.
        logger.error("[ChatRoutes] websocket_new_chat unexpected error: %s", exc)
        manager.disconnect(ws_key)


# ═════════════════════════════════════════════════════════════════════════════
# WS /ws/chat/{trip_id}?token=xxx&auto_msg=xxx
# ═════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws/chat/{trip_id}")
async def websocket_chat(
    trip_id:   str,
    websocket: WebSocket,
    token:     str          = Query(...),
    auto_msg:  str          = Query(default=None),
    db:        AsyncSession = Depends(get_db),
):
    user = verify_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    user_id = user["uid"]

    await manager.connect(trip_id, websocket)
    lock = manager.get_lock(trip_id)

    try:
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries)
                .selectinload(Itinerary.days)
                .selectinload(Day.stops),
                selectinload(Trip.conversation),
                selectinload(Trip.trip_profiles),
            )
            .where(
                Trip.trip_id == trip_id,
                Trip.user_id == user_id,
            )
        )
        trip = result.scalar_one_or_none()
        if not trip:
            await manager.send(trip_id, {"type": "error", "data": "Trip not found"})
            await websocket.close(code=4004)
            return

        conversation = await get_or_create_conversation(trip, user_id, db)
        await db.commit()

        # ── Initialize ai_session_id from the persisted DB value ────
        # This ensures that every subsequent call to process_message_stream
        # uses the same session_id, allowing the AI engine to find (or
        # rebuild) the correct ConversationState from Redis/DB.
        # On reconnection from chat history, the first message can attempt a
        # fast Redis lookup via resume_or_create(session_id=...) instead of
        # relying solely on the recovery_state fallback path.
        # The value gets updated after each process_message_stream call with
        # the live session_id from the AI engine and is re-persisted via
        # save_state_snapshot in the sync step.
        ai_session_id: Optional[str] = conversation.ai_session_id

        # ── Initialize itinerary card tracking for reopened conversations ──
        # _conversations_with_itinerary_card is an in-memory set that
        # prevents duplicate itinerary cards from being rendered.  When a
        # conversation with an existing itinerary is reopened, we must pre-
        # populate this set so the first follow-up message doesn't re-render
        # the itinerary card (see Flutter's _attachItinerary which
        # replaces assistant text with an itinerary card).
        if trip.status in (
            TripStatus.itinerary_draft,
            TripStatus.awaiting_booking,
            TripStatus.booking_pending,
            TripStatus.booking_confirmed,
            TripStatus.active,
            TripStatus.completed,
        ):
            _conversations_with_itinerary_card.add(conversation.conversation_id)
            logger.info(
                "[ChatRoutes] Initialized card tracking for reopened conversation %s "
                "(trip status=%s)",
                conversation.conversation_id, trip.status.value,
            )

        logger.info(
            "[DIAG][websocket_chat] INIT trip=%s conv=%s state_snapshot_phase=%s "
            "ai_session_id_from_db=%s trip_status=%s",
            trip_id, conversation.conversation_id,
            conversation.state_snapshot.get("phase") if conversation.state_snapshot else None,
            ai_session_id,
            trip.status.value if trip.status else None,
        )

        profile_data = await get_profile_data(user_id, trip.trip_id, db)

        if auto_msg and auto_msg.strip():
            async with lock:
                ai_session_id = await process_message_stream(
                    user_text=auto_msg.strip(),
                    trip=trip,
                    conversation=conversation,
                    profile_data=profile_data,
                    ws_key=trip_id,
                    db=db,
                    user_id=user_id,
                    token=token,
                    session_id=ai_session_id,
                )

        while True:
            data      = await websocket.receive_json()
            
            # ── Heartbeat ping/pong ────────────────────────────────────────
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            user_text = data.get("message", "").strip()
            
            # Extract image data if present
            image_bytes = None
            raw_image_data = data.get("image")
            if raw_image_data:
                try:
                    image_bytes = base64.b64decode(raw_image_data)
                except Exception as e:
                    logger.warning("[ChatRoutes] Failed to decode image data: %s", e)
            
            if not user_text and not image_bytes:
                continue

            # Use placeholder message for image-only uploads
            effective_message = user_text if user_text else "I uploaded an image for my trip."

            async with lock:
                ai_session_id = await process_message_stream(
                    user_text=effective_message,
                    trip=trip,
                    conversation=conversation,
                    profile_data=profile_data,
                    ws_key=trip_id,
                    db=db,
                    user_id=user_id,
                    token=token,
                    session_id=ai_session_id,
                    image_bytes=image_bytes,
                    image_data=raw_image_data,
                )

    except WebSocketDisconnect:
        manager.disconnect(trip_id)
    except Exception as exc:
        # Catch any unexpected runtime error (e.g. Starlette "WebSocket is not
        # connected. Need to call 'accept' first.") that would otherwise
        # crash the server process.
        logger.error("[ChatRoutes] websocket_chat unexpected error: %s", exc)
        manager.disconnect(trip_id)


# ═════════════════════════════════════════════════════════════════════════════
# GET /chat/{trip_id}/history
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/chat/{trip_id}/history")
async def get_history(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    trip_result = await db.execute(
        select(Trip).options(selectinload(Trip.conversation)).where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = trip_result.scalar_one_or_none()
    if not trip or not trip.conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = trip.conversation
    await db.refresh(conversation, ["messages"])

    messages = sorted(conversation.messages, key=lambda m: m.timestamp)
    # ── Deduplication (safety net) ────────────────────────────────────────
    # Remove only exact (sender, content) duplicates that may have been created
    # by an earlier bug in ``rebuild_conversation_state_from_db`` (mapped
    # "agent" DB → "user" ChatMessage role, causing sync_redis_to_db to
    # insert exact-duplicate user messages).
    #
    # We ONLY remove true duplicates (same sender + same content) and NEVER
    # drop cross-sender matches — a user and AI could legitimately say the
    # same text in different turns.
    seen_content: set = set()
    deduped = []
    for m in messages:
        key = (m.sender, m.content)
        if key not in seen_content:
            seen_content.add(key)
            deduped.append(m)

    result_messages = []
    for m in deduped:
        entry = {
            "message_id":      m.message_id,
            "conversation_id": m.conversation_id,
            "sender":          m.sender,
            "content":         m.content,
            "image_data":      m.image_data,
            "card_data":       m.card_data,
            "timestamp":       m.timestamp,
        }

        # ── Upgrade legacy card_data to canonical segments format ───────
        #    If card_data is an old-style dict (has "rendered_cards" key),
        #    convert it to the protocol format.  New responses already store
        #    canonical segments via build_history_payload().
        if m.card_data and isinstance(m.card_data, dict) and "rendered_cards" in m.card_data:
            try:
                legacy = m.card_data
                text = m.content or ""
                cards = []

                # Rebuild card list from legacy keys
                itinerary_data = legacy.get("itinerary_data")
                if itinerary_data:
                    cards.append({"card_type": ChatCardType.ITINERARY.value, "data": itinerary_data})

                hotel_data = legacy.get("hotel_options")
                if hotel_data:
                    cards.append({"card_type": ChatCardType.HOTEL_OPTIONS.value, "data": hotel_data})

                booking_data = legacy.get("booking_data")
                if booking_data:
                    cards.append({"card_type": ChatCardType.BOOKING.value, "data": booking_data})

                flight_data = legacy.get("flight_options")
                if flight_data:
                    cards.append({"card_type": ChatCardType.FLIGHT_OPTIONS.value, "data": flight_data})

                image_data = legacy.get("image_features")
                if image_data:
                    cards.append({"card_type": ChatCardType.IMAGE_FEATURES.value, "data": image_data})

                auxiliary = {}
                flight_booking = legacy.get("flight_booking")
                if flight_booking:
                    auxiliary["flight_booking"] = flight_booking

                entry["card_data"] = build_history_payload(
                    text=text,
                    cards=cards,
                    auxiliary=auxiliary if auxiliary else None,
                )
            except Exception as convert_err:
                logger.warning(
                    "[ChatRoutes] Failed to convert legacy card_data for msg %s: %s",
                    m.message_id, convert_err,
                )

        result_messages.append(entry)

    return result_messages


# ═════════════════════════════════════════════════════════════════════════════
# DELETE /chat/{trip_id}/clear
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# GET /chats/ — list all conversations for the current user
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/chats/")
async def list_chats(
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
    limit:        int          = Query(50, description="Max conversations to return"),
):
    """Return all conversations for the authenticated user, newest first.

    Each conversation includes:
      - conversation_id
      - trip_id          (if linked)
      - trip             (nested object with trip_id, trip_name, destination, status)
      - created_at       (ISO-8601)
      - last_message     (snippet of the most recent message)
      - last_message_at  (ISO-8601)
    """
    svc = ChatService(db)
    return await svc.get_user_conversations(current_user["uid"], limit=limit)


@router.delete("/chat/{trip_id}/clear")
async def clear_chat(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    trip_result = await db.execute(
        select(Trip).options(selectinload(Trip.conversation)).where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = trip_result.scalar_one_or_none()
    if not trip or not trip.conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation = trip.conversation

    # ── 1. Delete DB messages ───────────────────────────────────────────────
    await db.execute(
        delete(Message).where(
            Message.conversation_id == conversation.conversation_id
        )
    )

    # ── 2. Clear Redis conversation state ────────────────────────────────────
    # Without this, the next call to sync_redis_to_db would re-insert all old
    # messages into the DB (offset-based sync sees db_count=0 and treats all
    # Redis history as new).
    try:
        from ai_engine.conversation.redis_memory import get_session_manager
        redis_mgr = await get_session_manager()
        if redis_mgr.is_connected:
            # Delete the state stored under conversation_id (the effective session_id)
            await redis_mgr.delete(conversation.conversation_id)
            # Also delete any stale session stored as the old ai_session_id
            if conversation.ai_session_id and conversation.ai_session_id != conversation.conversation_id:
                await redis_mgr.delete(conversation.ai_session_id)
    except Exception as redis_err:
        logger.warning("[ChatRoutes] Failed to clear Redis session (non-fatal): %s", redis_err)

    # ── 3. Reset conversation snapshot so next message starts fresh ──────────
    conversation.state_snapshot = None
    conversation.ai_session_id = None

    await db.commit()
    return {"message": "Chat cleared successfully"}
