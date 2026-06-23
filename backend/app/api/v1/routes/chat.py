import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import uuid

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.firebase import verify_token
from app.core.security import get_current_user
from app.models.enums import TripStatus, ItineraryStatus
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.chat import Conversation, Message
from app.models.profile import TripProfile
from app.services.chat_service import ChatService
from app.ws.manager import manager

router = APIRouter()


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
                    "lng":           data.get("lng"),
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
    if updated_actions:
        trip.updated_at = datetime.utcnow()

        profile_result = await db.execute(
            select(TripProfile).where(TripProfile.trip_id == trip.trip_id)
        )
        for prof in profile_result.scalars().all():
            prof.updated_at = datetime.utcnow()

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
            pass

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
) -> Optional[str]:
    """Process a message with streaming token-by-token response.

    Returns the AI engine session_id for subsequent calls.
    """
    svc = ChatService(db)

    # ── Save user message ─────────────────────────────────────────────────
    await svc.save_user_message(conversation.conversation_id, user_text)
    await db.commit()

    # ── typing ───────────────────────────────────────────────────────────
    await manager.send(ws_key, {"type": "typing"})

    # ── Stream AI response ───────────────────────────────────────────────
    full_response = ""
    actions       = []
    ai_session_id = None
    approve_action = None  # Track if this is an approval result
    profile_from_ai = None  # Track profile data from the AI engine

    try:
        from ai_engine.chat.conversation_agent import handle_chat_stream

        async for chunk in handle_chat_stream(
            user_id=user_id,
            user_message=user_text,
            token=token,
            session_id=session_id,
        ):
            event_type = chunk.get("type")

            if event_type == "session":
                session_data  = chunk.get("data", {})
                ai_session_id = session_data.get("session_id")

            elif event_type == "text":
                content        = chunk.get("content", "")
                full_response += content
                await manager.send(ws_key, {"type": "token", "data": content})

            elif event_type == "phase":
                await manager.send(ws_key, chunk)

                # If phase is COMPLETED, this is an approval — update DB
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
                    approve_action = {
                        "type": "APPROVE_TRIP",
                    }
                elif result.get("itinerary"):
                    actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
                    # Capture profile data from the AI engine for TripProfile persistence
                    if result.get("profile"):
                        profile_from_ai = result["profile"]

            elif event_type == "done":
                await manager.send(ws_key, {"type": "done", "data": None})

    except Exception as exc:
        logger.exception("[ChatRoutes] AI engine streaming failed: %s", exc)
        error_response = ChatService.build_error_response()
        full_response  = error_response["message"]
        actions        = []
        ai_session_id  = None
        approve_action = None
        await manager.send(ws_key, {"type": "token", "data": full_response})
        await manager.send(ws_key, {"type": "done", "data": None})

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

        now = datetime.utcnow()

        # Update trip: status → active, approved_at → now
        # (updated_at is handled by onupdate=func.now() in the model)
        trip.status = TripStatus.active
        trip.approved_at = now

        # Update itinerary: status → active
        # (updated_at is handled by onupdate=func.now() in the model)
        if trip.itineraries:
            for itin in trip.itineraries:
                itin.status = ItineraryStatus.active

        # Touch trip_profile updated_at
        if trip.trip_profiles:
            for prof in trip.trip_profiles:
                prof.updated_at = now

        logger.info(
            "[ChatRoutes] Trip %s approved — status=active, approved_at=%s",
            trip.trip_id, trip.approved_at,
        )

        was_approved = True

    # ── Execute actions ──────────────────────────────────────────────────
    updated_actions = []
    stops_created = 0
    if actions:
        # *** التعديل: جيب الـ trip مع كل العلاقات دفعة واحدة بدل db.refresh ***
        # عشان itinerary.days كانت بتعمل lazy load → crash في async context
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

        # Handle CREATE_TRIP for existing trips — update the itinerary
        # with new stops from the AI result instead of creating a new trip.
        create_action = next((a for a in actions if a.get("type") == "CREATE_TRIP"), None)
        if create_action:
            itinerary_data = create_action.get("data", {})
            days_data = itinerary_data.get("days", [])
            if days_data and trip.itineraries:
                itinerary = trip.itineraries[0]

                # Increment version number when updating existing itinerary
                # (updated_at is handled by onupdate=func.now() in the model)
                itinerary.version_number = (itinerary.version_number or 1) + 1

                from app.services.itinerary_service import ItineraryService
                itin_svc = ItineraryService(db)

                # Delete existing stops so we can replace with new ones
                for day_obj in itinerary.days:
                    await db.execute(
                        delete(ItineraryStop).where(ItineraryStop.day_id == day_obj.day_id)
                    )
                await db.flush()

                # Create fresh stops from the AI result
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

                # Touch trip.updated_at when itinerary changes
                trip.updated_at = datetime.utcnow()

                # Touch trip_profile updated_at when itinerary changes
                if trip.trip_profiles:
                    for prof in trip.trip_profiles:
                        prof.updated_at = datetime.utcnow()

            # ── Persist TripProfile from AI profile data (always, regardless of days_data) ──
            # The AI engine returns profile data in the result event.
            # Create or update the TripProfile so it stays in sync with the AI engine.
            if profile_from_ai:
                existing_profile = trip.trip_profiles[0] if trip.trip_profiles else None
                if existing_profile:
                    _update_profile_from_ai(existing_profile, profile_from_ai)
                    existing_profile.updated_at = datetime.utcnow()
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

                # Refresh local trip_profiles so subsequent code sees the profile
                if not trip.trip_profiles:
                    trip.trip_profiles = [existing_profile] if existing_profile else [new_profile]

        # Execute remaining non-CREATE_TRIP actions (ADD_ACTIVITY, etc.)
        remaining_actions = [a for a in actions if a.get("type") != "CREATE_TRIP"]
        if remaining_actions:
            updated_actions = await execute_actions(remaining_actions, trip, db)

    if stops_created > 0:
        logger.info(
            "[ChatRoutes] Updated itinerary %s with %d stops from AI result",
            trip.itineraries[0].itinerary_id if trip.itineraries else "?",
            stops_created,
        )

    # ── Save AI response to DB ───────────────────────────────────────────
    if full_response:
        await svc.save_agent_message(conversation.conversation_id, full_response)

    # ── Sync Redis state to DB ────────────────────────────────────────────
    if ai_session_id:
        try:
            from ai_engine.memory.redis_memory import get_session_manager
            redis_manager = await get_session_manager()
            if redis_manager.is_connected:
                redis_state = await redis_manager.load(ai_session_id)
                if redis_state and redis_state.history:
                    redis_msgs = [m.to_dict() for m in redis_state.history]
                    await svc.sync_redis_to_db(conversation.conversation_id, redis_msgs)
        except Exception as sync_err:
            logger.warning("[ChatRoutes] Redis sync failed (non-fatal): %s", sync_err)

    await db.commit()

    # ── Notify Flutter that trip was approved (after commit) ──────────────
    if was_approved:
        await manager.send(ws_key, {"type": "trip_approved"})

    # ── Notify Flutter of actions ─────────────────────────────────────────
    if updated_actions:
        await manager.send(ws_key, {"type": "actions", "data": updated_actions})
        await manager.send(ws_key, {"type": "itinerary_updated"})

    return ai_session_id


# ═════════════════════════════════════════════════════════════════════════════
# WS /ws/chat/new?token=xxx
# سيناريو 2: شات مباشر بدون فورم
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
        # ── State ────────────────────────────────────────────────────────
        trip:             Trip         = None
        conversation:     Conversation = None
        profile_data:     dict         = {}
        history_list:     list         = []
        pending_messages: list         = []
        ai_session_id:    Optional[str] = None

        while True:
            data      = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                continue

            # FIX: svc defined at the top of every loop iteration
            svc = ChatService(db)

            # ══════════════════════════════════════════════════════════════
            # لو Trip موجود خلاص → استخدم process_message_stream
            # ══════════════════════════════════════════════════════════════
            if trip and conversation:
                lock = manager.get_lock(ws_key)
                async with lock:
                    ai_session_id = await process_message_stream(
                        user_text=user_text,
                        trip=trip,
                        conversation=conversation,
                        profile_data=profile_data,
                        ws_key=ws_key,
                        db=db,
                        user_id=user_id,
                        token=token,
                        session_id=ai_session_id,
                    )

                history_list.append({"role": "user", "content": user_text})
                if len(history_list) > 20:
                    history_list = history_list[-20:]
                continue

            # ══════════════════════════════════════════════════════════════
            # لسه مفيش Trip → نكلم الـ AI ونشوف لو هيعمل CREATE_TRIP
            # ══════════════════════════════════════════════════════════════

            pending_messages.append({"role": "user", "content": user_text})

            await manager.send(ws_key, {"type": "typing"})

            full_response = ""
            actions       = []
            profile_data_from_ai = None

            try:
                from ai_engine.chat.conversation_agent import handle_chat_stream

                async for chunk in handle_chat_stream(
                    user_id=user_id,
                    user_message=user_text,
                    token=token,
                ):
                    event_type = chunk.get("type")

                    if event_type == "session":
                        session_data  = chunk.get("data", {})
                        ai_session_id = session_data.get("session_id")

                    elif event_type == "text":
                        content        = chunk.get("content", "")
                        full_response += content
                        await manager.send(ws_key, {"type": "token", "data": content})

                    elif event_type == "phase":
                        await manager.send(ws_key, chunk)

                    elif event_type == "result":
                        result         = chunk.get("data", {})
                        result_message = result.get("message", "")
                        if result_message:
                            full_response = result_message
                        if result.get("itinerary"):
                            actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
                        if result.get("profile"):
                            profile_data_from_ai = result["profile"]

                    elif event_type == "done":
                        await manager.send(ws_key, {"type": "done"})

            except Exception as exc:
                logger.exception("[ChatRoutes] AI engine streaming failed in websocket_new_chat: %s", exc)
                error_response = ChatService.build_error_response()
                full_response  = error_response["message"]
                actions        = []
                await manager.send(ws_key, {"type": "token", "data": full_response})
                await manager.send(ws_key, {"type": "done"})

            # ══════════════════════════════════════════════════════════════
            # شوف لو فيه CREATE_TRIP
            # ══════════════════════════════════════════════════════════════
            for action in actions:
                if action.get("type") == "CREATE_TRIP" and not trip:
                    ai_result = {"itinerary": action.get("data", {})}
                    if profile_data_from_ai:
                        ai_result["profile"] = profile_data_from_ai
                    created = await svc.create_trip_from_ai_result(
                        user_id,
                        ai_result,
                    )

                    trip         = created["trip"]
                    conversation = created["conversation"]

                    # ── احفظ كل الرسايل المعلقة ───────────────────────────
                    for msg in pending_messages:
                        await svc.save_message(
                            conversation_id=conversation.conversation_id,
                            sender="user" if msg["role"] == "user" else "agent",
                            content=msg["content"],
                        )
                    pending_messages = []

                    await db.commit()

                    # ── بلّغ Flutter بالـ trip_id والـ itinerary ──────────
                    await manager.send(ws_key, {
                        "type":         "trip_created",
                        "trip_id":      trip.trip_id,
                        "itinerary_id": created["itinerary"].itinerary_id,
                    })

                    profile_data = await get_profile_data(user_id, trip.trip_id, db)

                    # ── حدّث ws_key ──────────────────────────────────────
                    manager.disconnect(ws_key)
                    ws_key = trip.trip_id
                    await manager.connect_existing(ws_key, websocket)

                    break

            # ══════════════════════════════════════════════════════════════
            # نفذ باقي الـ Actions (ADD_ACTIVITY, etc.)
            # ══════════════════════════════════════════════════════════════
            non_create_actions = [a for a in actions if a.get("type") != "CREATE_TRIP"]
            updated_actions    = []

            if trip and non_create_actions:
                updated_actions = await execute_actions(non_create_actions, trip, db)
                await db.commit()

            # ── احفظ رد الـ AI في pending أو في الـ DB لو conversation موجودة ──
            pending_messages.append({"role": "assistant", "content": full_response})

            if conversation and full_response:
                await svc.save_agent_message(conversation.conversation_id, full_response)
                await db.commit()

            # ── بلّغ Flutter لو في تغييرات ────────────────────────────────
            if updated_actions:
                await manager.send(ws_key, {"type": "actions", "data": updated_actions})
                await manager.send(ws_key, {"type": "itinerary_updated"})

            # ── حدّث history ─────────────────────────────────────────────
            history_list.append({"role": "user",      "content": user_text})
            history_list.append({"role": "assistant", "content": full_response})
            if len(history_list) > 20:
                history_list = history_list[-20:]

    except WebSocketDisconnect:
        manager.disconnect(ws_key)


# ═════════════════════════════════════════════════════════════════════════════
# WS /ws/chat/{trip_id}?token=xxx&auto_msg=xxx
# سيناريو 1: الفورم → الشات
# ═════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws/chat/{trip_id}")
async def websocket_chat(
    trip_id:   str,
    websocket: WebSocket,
    token:     str          = Query(...),
    auto_msg:  str          = Query(default=None),
    db:        AsyncSession = Depends(get_db),
):
    # ── Auth ─────────────────────────────────────────────────────────────
    user = verify_token(token)
    if not user:
        await websocket.close(code=4001)
        return

    user_id = user["uid"]

    await manager.connect(trip_id, websocket)
    lock = manager.get_lock(trip_id)

    try:
        # ── State for session_id propagation ──────────────────────────────
        ai_session_id: Optional[str] = None

        # ── جيب الـ Trip ─────────────────────────────────────────────────
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

        # ── جيب أو أنشئ Conversation ─────────────────────────────────────
        conversation = await get_or_create_conversation(trip, user_id, db)
        await db.commit()

        # ── جيب الـ Profile ──────────────────────────────────────────────
        profile_data = await get_profile_data(user_id, trip.trip_id, db)

        # ══════════════════════════════════════════════════════════════════
        # AUTO-GENERATE: لو Flutter بعت auto_msg → نبعته للـ AI فوراً
        # ══════════════════════════════════════════════════════════════════
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

        # ── الـ Loop العادي ───────────────────────────────────────────────
        while True:
            data      = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                continue

            async with lock:
                ai_session_id = await process_message_stream(
                    user_text=user_text,
                    trip=trip,
                    conversation=conversation,
                    profile_data=profile_data,
                    ws_key=trip_id,
                    db=db,
                    user_id=user_id,
                    token=token,
                    session_id=ai_session_id,
                )

    except WebSocketDisconnect:
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
    return [
        {
            "message_id":      m.message_id,
            "conversation_id": m.conversation_id,
            "sender":          m.sender,
            "content":         m.content,
            "timestamp":       m.timestamp,
        }
        for m in messages
    ]


# ═════════════════════════════════════════════════════════════════════════════
# DELETE /chat/{trip_id}/clear
# ═════════════════════════════════════════════════════════════════════════════

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

    await db.execute(
        delete(Message).where(
            Message.conversation_id == conversation.conversation_id
        )
    )
    await db.commit()
    return {"message": "Chat cleared successfully"}