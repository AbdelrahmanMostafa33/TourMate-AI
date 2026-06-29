import base64
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
from app.services.image_service import ImageService
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

    Returns the AI engine session_id for subsequent calls.
    """
    svc = ChatService(db)

    # ── Save user message (with image if provided) ────────────────────────
    await svc.save_user_message(conversation.conversation_id, user_text, image_data=image_data)
    await db.commit()

    # ── typing ───────────────────────────────────────────────────────────
    await manager.send(ws_key, {"type": "typing"})

    # ── Stream AI response ───────────────────────────────────────────────
    full_response = ""
    actions       = []
    ai_session_id = None
    approve_action = None
    profile_from_ai = None
    pool_state_from_ai = None
    image_features_from_result = None

    initial_pool_state = await svc.load_pool_for_trip(trip.trip_id)

    try:
        from ai_engine.conversation.orchestrator import handle_chat_stream

        async for chunk in handle_chat_stream(
            user_id=user_id,
            user_message=user_text,
            image_bytes=image_bytes,
            token=token,
            session_id=session_id,
            initial_pool_state=initial_pool_state,
        ):
            event_type = chunk.get("type")

            if event_type == "session":
                session_data  = chunk.get("data", {})
                ai_session_id = session_data.get("session_id")

            elif event_type == "text":
                content        = chunk.get("content", "")
                full_response += content
                await manager.send(ws_key, {"type": "token", "data": content})

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
                    approve_action = {
                        "type": "APPROVE_TRIP",
                    }
                elif result.get("itinerary"):
                    actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
                    # Send structured itinerary data to Flutter for card rendering
                    await manager.send(ws_key, {
                        "type": "itinerary_data",
                        "data": result["itinerary"],
                    })
                    if result.get("profile"):
                        profile_from_ai = result["profile"]
                    if result.get("pool_state"):
                        pool_state_from_ai = result["pool_state"]

                # Capture image_features for DB persistence later
                image_features_from_result = result.get("image_features")

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

        from sqlalchemy.sql import func as sqlfunc

        # Update trip: status → active, approved_at → now (Cairo via DB)
        trip.status      = TripStatus.active
        trip.approved_at = sqlfunc.now()

        # Update itinerary: status → active (updated_at handled by onupdate)
        if trip.itineraries:
            for itin in trip.itineraries:
                itin.status = ItineraryStatus.active

        # Touch trip_profile updated_at (Cairo via DB)
        if trip.trip_profiles:
            for prof in trip.trip_profiles:
                prof.updated_at = sqlfunc.now()

        logger.info(
            "[ChatRoutes] Trip %s approved — status=active",
            trip.trip_id,
        )

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

    # ── Save AI response to DB ───────────────────────────────────────
    if full_response:
        await svc.save_agent_message(conversation.conversation_id, full_response)

    # ── Sync Redis state to DB ────────────────────────────────────────────
    if ai_session_id:
        try:
            from ai_engine.conversation.redis_memory import get_session_manager
            redis_manager = await get_session_manager()
            if redis_manager.is_connected:
                redis_state = await redis_manager.load(ai_session_id)
                if redis_state and redis_state.history:
                    redis_msgs = [m.to_dict() for m in redis_state.history]
                    await svc.sync_redis_to_db(conversation.conversation_id, redis_msgs)
        except Exception as sync_err:
            logger.warning("[ChatRoutes] Redis sync failed (non-fatal): %s", sync_err)

    # ── Persist image features to DB (non-critical) ──────────────────────
    if image_features_from_result and image_features_from_result.has_signal:
        try:
            img_svc = ImageService(db)
            await img_svc.create_image_with_features(
                trip_id=trip.trip_id,
                vision_features=image_features_from_result,
            )
            await db.commit()
        except Exception as img_err:
            logger.warning("[ChatRoutes] Failed to persist image features (non-fatal): %s", img_err)
            await db.rollback()

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
                        await manager.send(ws_key, {"type": "token", "data": content})

                    elif event_type == "progress":
                        await manager.send(ws_key, chunk)

                    elif event_type == "phase":
                        await manager.send(ws_key, chunk)

                    elif event_type == "result":
                        result         = chunk.get("data", {})
                        result_message = result.get("message", "")
                        if result_message:
                            full_response = result_message
                        if result.get("itinerary"):
                            actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
                            # Send structured itinerary data to Flutter for card rendering
                            await manager.send(ws_key, {
                                "type": "itinerary_data",
                                "data": result["itinerary"],
                            })
                        if result.get("profile"):
                            profile_data_from_ai = result["profile"]
                        if result.get("pool_state"):
                            pool_state_from_ai = result["pool_state"]

                        # Capture image_features for DB persistence later
                        image_features_from_result = result.get("image_features")

                    elif event_type == "done":
                        await manager.send(ws_key, {"type": "done"})

            except Exception as exc:
                logger.exception("[ChatRoutes] AI engine streaming failed in websocket_new_chat: %s", exc)
                error_response = ChatService.build_error_response()
                full_response  = error_response["message"]
                actions        = []
                await manager.send(ws_key, {"type": "token", "data": full_response})
                await manager.send(ws_key, {"type": "done"})

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

                        for msg in pending_messages:
                            await svc.save_message(
                                conversation_id=conversation.conversation_id,
                                sender="user" if msg["role"] == "user" else "agent",
                                content=msg["content"],
                                image_data=msg.get("image_data"),
                            )
                        pending_messages = []

                        # ── Persist image features if available ──────────────
                        if image_features_from_result and image_features_from_result.has_signal:
                            try:
                                img_svc = ImageService(db)
                                await img_svc.create_image_with_features(
                                    trip_id=trip.trip_id,
                                    vision_features=image_features_from_result,
                                )
                            except Exception as img_err:
                                logger.warning(
                                    "[ChatRoutes] Failed to persist image features (non-fatal): %s",
                                    img_err,
                                )

                        await db.commit()

                        await manager.send(ws_key, {
                            "type":         "trip_created",
                            "trip_id":      trip.trip_id,
                            "itinerary_id": created["itinerary"].itinerary_id,
                        })

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
                await svc.save_agent_message(conversation.conversation_id, full_response)
                await db.commit()

            if updated_actions:
                await manager.send(ws_key, {"type": "actions", "data": updated_actions})
                await manager.send(ws_key, {"type": "itinerary_updated"})

            history_list.append({"role": "user",      "content": effective_message})
            history_list.append({"role": "assistant", "content": full_response})
            if len(history_list) > 20:
                history_list = history_list[-20:]

    except WebSocketDisconnect:
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
        ai_session_id: Optional[str] = None

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
            "image_data":      m.image_data,
            "timestamp":       m.timestamp,
        }
        for m in messages
    ]


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

    await db.execute(
        delete(Message).where(
            Message.conversation_id == conversation.conversation_id
        )
    )
    await db.commit()
    return {"message": "Chat cleared successfully"}