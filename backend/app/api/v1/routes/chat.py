from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
import uuid

from app.core.database import get_db
from app.core.firebase import verify_token
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.chat import Conversation, Message
from app.models.profile import TripProfile
from app.ws.manager import manager
from datetime import time as dt_time

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# Helper: صورة الرحلة للـ AI
# ═════════════════════════════════════════════════════════════════════════════

def build_trip_snapshot(trip: Trip) -> dict:
    days_data = []
    for itinerary in trip.itineraries:
        for day in itinerary.days:
            days_data.append({
                "day_id":     day.day_id,
                "day_number": day.day_number,
                "date":       str(day.date) if day.date else None,
                "stops": [
                    {
                        "stop_id":          stop.stop_id,
                        "place_id":         stop.place_id,
                        "scheduled_time":   str(stop.scheduled_time) if stop.scheduled_time else None,
                        "duration_minutes": stop.duration_minutes,
                        "order_in_day":     stop.order_in_day,
                        "travel_mode":      stop.travel_mode.value if stop.travel_mode else None,
                        "estimated_cost":   stop.estimated_cost,
                        "ai_notes":         stop.ai_notes,
                        "user_notes":       stop.user_notes,
                        "status":           stop.status.value if stop.status else None,
                    }
                    for stop in day.stops
                ],
            })
    return {
        "trip_id":     trip.trip_id,
        "destination": trip.destination,
        "days":        days_data,
    }

#--------------------------------------------------------


def parse_time(raw_time) -> dt_time | None:
    """حوّل أي شكل time لـ datetime.time object"""
    if raw_time is None:
        return None
    if isinstance(raw_time, dt_time):
        return raw_time
    if isinstance(raw_time, str):
        try:
            parts = raw_time.strip().split(":")
            return dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return None
    return None
# ═════════════════════════════════════════════════════════════════════════════
# Helper: نفذ الـ actions على الـ DB
# ═════════════════════════════════════════════════════════════════════════════

async def execute_actions(actions: list, trip: Trip, db: AsyncSession) -> list:
    updated_actions = []

    # Get the first itinerary for this trip (or create one)
    if not trip.itineraries:
        itinerary = Itinerary(
            itinerary_id = str(uuid.uuid4()),
            trip_id      = trip.trip_id,
            title        = f"Trip to {trip.destination}",
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
            all_days = [d for it in trip.itineraries for d in it.days]
            existing = next((d for d in all_days if d.day_number == day_number), None)
            if not existing:
                new_day = Day(
                    itinerary_id = itinerary.itinerary_id,
                    day_number   = day_number,
                    date         = data.get("date"),
                )
                db.add(new_day)
                await db.flush()
                action["generated_id"] = new_day.day_id

        # ── ADD_ACTIVITY ─────────────────────────────────────────────────
        elif action_type == "ADD_ACTIVITY":
            day_number = data.get("day_number", 1)
            all_days = [d for it in trip.itineraries for d in it.days]
            day = next((d for d in all_days if d.day_number == day_number), None)
            if not day:
                day = Day(itinerary_id=itinerary.itinerary_id, day_number=day_number)
                db.add(day)
                await db.flush()

            scheduled_time = parse_time(data.get("time"))
            new_stop = ItineraryStop(
                day_id           = day.day_id,
                place_snapshot   = {"name": data.get("name", ""), "type": data.get("type", "attraction"), "location_name": data.get("location_name"), "lat": data.get("lat"), "lng": data.get("lng")},
                scheduled_time   = scheduled_time,
                duration_minutes = int(data["duration_hours"] * 60) if data.get("duration_hours") else None,
                order_in_day     = data.get("order_in_day", 0),
                ai_notes         = data.get("notes"),
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
                    if data.get("time"):
                        stop.scheduled_time = parse_time(data["time"])
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
            if data.get("budget"):
                trip.budget = data["budget"]
            await db.flush()

        updated_actions.append(action)

    return updated_actions


# ═════════════════════════════════════════════════════════════════════════════
# Helper: جيب أو أنشئ Conversation
# ═════════════════════════════════════════════════════════════════════════════

async def get_or_create_conversation(
    trip:    Trip,
    user_id: str,
    db:      AsyncSession,
) -> Conversation:
    """Get or create a conversation for a trip via the Trip.conversation FK."""
    if trip.conversation:
        return trip.conversation

    conversation = Conversation(
        conversation_id = str(uuid.uuid4()),
        user_id         = user_id,
    )
    db.add(conversation)
    await db.flush()

    # Link conversation to trip via FK
    trip.conversation_id = conversation.conversation_id
    await db.flush()

    return conversation


# ═════════════════════════════════════════════════════════════════════════════
# Helper: get BehavioralProfile
# ═════════════════════════════════════════════════════════════════════════════

async def get_profile_data(user_id: str, trip_id: str, db: AsyncSession) -> dict:
    """Get trip profile data for the AI pipeline."""
    result = await db.execute(
        select(TripProfile).where(TripProfile.trip_id == trip_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return {}

    return {
        # ── Preference ENUMs ─────────────────────────────────────────
        "budget_level":            profile.budget_level,
        "travel_style":            profile.travel_style,
        "pace":                    profile.pace,

        # ── Lists ───────────────────────────────────────────────────
        "interests":               profile.interests or [],
        "food_preferences":        profile.food_preferences or [],
        "accommodation_preferences": profile.accommodation_preferences or [],

        # ── AI Scoring ───────────────────────────────────────────────
        "luxury_score":            profile.luxury_score,
        "culture_score":           profile.culture_score,
        "adventure_score":         profile.adventure_score,
        "shopping_score":          profile.shopping_score,
        "family_score":            profile.family_score,
        "confidence":              profile.confidence,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helper: معالجة رسالة واحدة (مشتركة بين الـ endpoints)
# ═════════════════════════════════════════════════════════════════════════════

async def process_message(
    user_text:    str,
    trip:         Trip,
    conversation: Conversation,
    profile_data: dict,
    ws_key:       str,
    db:           AsyncSession,
    user_id:      str,
    token:        str,
):

    # ── حفظ رسالة اليوزر ─────────────────────────────────────────────────
    user_msg = Message(
        message_id      = str(uuid.uuid4()),
        conversation_id = conversation.conversation_id,
        sender          = "user",
        content         = user_text,
    )
    db.add(user_msg)
    await db.commit()

    # ── جيب الـ history ──────────────────────────────────────────────────
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.conversation_id)
        .order_by(Message.timestamp.desc())
        .limit(10)
    )
    history_list = [
        {"sender": m.sender, "content": m.content}
        for m in reversed(history_result.scalars().all())
    ]

    # ── جيب Trip snapshot محدّث ──────────────────────────────────────────
    trip_snapshot = build_trip_snapshot(trip)

    # ── typing ───────────────────────────────────────────────────────────
    await manager.send(ws_key, {"type": "typing"})

    # ── كلم الـ AI ───────────────────────────────────────────────────────
    full_response = ""
    actions       = []

    try:
        from ai_engine.chat.chat_handler import handle_chat
        result = await handle_chat(
            user_id=user_id,
            user_message=user_text,
            token=token,
        )
        full_response = result.get("message", "")
        if result.get("itinerary"):
            actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
        await manager.send(ws_key, {
            "type": "token",
            "data": full_response,
        })

    except Exception:
        # ══════════════════════════════════════════════════════════════
        # MOCK placeholder
        # ══════════════════════════════════════════════════════════════
        full_response = (
            "Here's your trip plan! 🎉\n\n"
            "**Day 1:**\n"
            "- 🏨 09:00 Check in at Hotel\n"
            "- 🏛️ 10:30 City Walking Tour\n"
            "- 🍽️ 13:00 Lunch at Local Restaurant\n"
            "- 🏛️ 15:00 Museum Visit\n"
        )

        for token_chunk in full_response.split():
            await manager.send(ws_key, {
                "type": "token",
                "data": token_chunk + " ",
            })

        actions = [
            {
                "type": "ADD_ACTIVITY",
                "data": {
                    "day_number":    1,
                    "name":          "Check in at Hotel",
                    "type":          "hotel",
                    "time":          "09:00",
                    "duration_hours": 1.0,
                    "order_in_day":  1,
                    "location_name": "City Center Hotel",
                    "lat":           30.0444,
                    "lng":           31.2357,
                    "notes":         "Central location",
                },
            },
            {
                "type": "ADD_ACTIVITY",
                "data": {
                    "day_number":    1,
                    "name":          "City Walking Tour",
                    "type":          "attraction",
                    "time":          "10:30",
                    "duration_hours": 2.0,
                    "order_in_day":  2,
                    "location_name": "Old Town Square",
                    "lat":           30.0459,
                    "lng":           31.2243,
                    "notes":         "Guided tour of main sights",
                },
            },
            {
                "type": "ADD_ACTIVITY",
                "data": {
                    "day_number":    1,
                    "name":          "Lunch at Local Restaurant",
                    "type":          "restaurant",
                    "time":          "13:00",
                    "duration_hours": 1.5,
                    "order_in_day":  3,
                    "location_name": "Local Restaurant",
                    "lat":           30.0500,
                    "lng":           31.2450,
                    "notes":         "Try the local cuisine",
                },
            },
            {
                "type": "ADD_ACTIVITY",
                "data": {
                    "day_number":    1,
                    "name":          "Museum Visit",
                    "type":          "attraction",
                    "time":          "15:00",
                    "duration_hours": 2.0,
                    "order_in_day":  4,
                    "location_name": "National Museum",
                    "lat":           30.0478,
                    "lng":           31.2336,
                    "notes":         "History and culture",
                },
            },
        ]

    # ── done ─────────────────────────────────────────────────────────────
    await manager.send(ws_key, {"type": "done", "data": None})

    # ── نفذ الـ actions ──────────────────────────────────────────────────
    updated_actions = []
    if actions:
        await db.refresh(trip, ["itineraries"])
        updated_actions = await execute_actions(actions, trip, db)

    # ── احفظ رد الـ AI ───────────────────────────────────────────────────
    ai_msg = Message(
        message_id      = str(uuid.uuid4()),
        conversation_id = conversation.conversation_id,
        sender          = "agent",
        content         = full_response,
    )
    db.add(ai_msg)
    await db.commit()

    # ── بلّغ Flutter ─────────────────────────────────────────────────────
    if updated_actions:
        await manager.send(ws_key, {
            "type": "actions",
            "data": updated_actions,
        })
        await manager.send(ws_key, {"type": "itinerary_updated"})




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

        while True:
            data      = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                continue

            # ══════════════════════════════════════════════════════════════
            # لو Trip موجود خلاص → استخدم process_message العادية
            # ══════════════════════════════════════════════════════════════
            if trip and conversation:
                lock = manager.get_lock(ws_key)
                async with lock:
                    await process_message(
                        user_text    = user_text,
                        trip         = trip,
                        conversation = conversation,
                        profile_data = profile_data,
                        ws_key       = ws_key,
                        db           = db,
                        user_id      = user_id,
                        token        = token,
                    )

                # ── حدّث history ─────────────────────────────────────────
                history_list.append({"role": "user", "content": user_text})
                if len(history_list) > 20:
                    history_list = history_list[-20:]
                continue

            # ══════════════════════════════════════════════════════════════
            # لسه مفيش Trip → نكلم الـ AI ونشوف لو هيعمل CREATE_TRIP
            # ══════════════════════════════════════════════════════════════

            pending_messages.append({"role": "user", "content": user_text})

            # ── typing ───────────────────────────────────────────────────
            await manager.send(ws_key, {"type": "typing"})

            # ── كلم الـ AI ───────────────────────────────────────────────
            full_response = ""
            actions       = []

            try:
                from ai_engine.chat.chat_handler import handle_chat
                result = await handle_chat(
                    user_id=user_id,
                    user_message=user_text,
                    token=token,
                )
                full_response = result.get("message", "")
                if result.get("itinerary"):
                    actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
                await manager.send(ws_key, {
                    "type": "token",
                    "data": full_response,
                })

            except Exception:
                # ══════════════════════════════════════════════════════════
                # MOCK: placeholder لحد ما الـ AI Team يخلصوا
                # ══════════════════════════════════════════════════════════
                full_response = (
                    "Sounds great! Let me plan that for you 🎉\n\n"
                    "**Day 1:**\n"
                    "- 🏨 09:00 Check in at Hotel\n"
                    "- 🏛️ 10:30 City Walking Tour\n"
                    "- 🍽️ 13:00 Lunch at Local Restaurant\n"
                )

                for token_chunk in full_response.split():
                    await manager.send(ws_key, {
                        "type": "token",
                        "data": token_chunk + " ",
                    })

                mock_start = date.today() + timedelta(days=7)
                mock_days  = 3

                actions = [
                    {
                        "type": "CREATE_TRIP",
                        "data": {
                            "destination":         "Cairo, Egypt",
                            "start_date":          str(mock_start),
                            "end_date":            str(mock_start + timedelta(days=mock_days - 1)),
                            "number_of_travelers": 1,
                        },
                    },
                    {
                        "type": "ADD_ACTIVITY",
                        "data": {
                            "day_number":    1,
                            "name":          "Check in at Hotel",
                            "type":          "hotel",
                            "time":          "09:00",
                            "duration_hours": 1.0,
                            "order_in_day":  1,
                            "location_name": "City Center Hotel",
                            "lat":           30.0444,
                            "lng":           31.2357,
                            "notes":         "Central location",
                        },
                    },
                    {
                        "type": "ADD_ACTIVITY",
                        "data": {
                            "day_number":    1,
                            "name":          "City Walking Tour",
                            "type":          "attraction",
                            "time":          "10:30",
                            "duration_hours": 2.0,
                            "order_in_day":  2,
                            "location_name": "Old Town Square",
                            "lat":           30.0459,
                            "lng":           31.2243,
                            "notes":         "Guided tour",
                        },
                    },
                    {
                        "type": "ADD_ACTIVITY",
                        "data": {
                            "day_number":    1,
                            "name":          "Lunch at Local Restaurant",
                            "type":          "restaurant",
                            "time":          "13:00",
                            "duration_hours": 1.5,
                            "order_in_day":  3,
                            "location_name": "Local Restaurant",
                            "lat":           30.0500,
                            "lng":           31.2450,
                            "notes":         "Try the local food",
                        },
                    },
                ]

            # ── done ─────────────────────────────────────────────────────
            await manager.send(ws_key, {"type": "done"})

            # ══════════════════════════════════════════════════════════════
            # شوف لو فيه CREATE_TRIP
            # ══════════════════════════════════════════════════════════════
            for action in actions:
                if action.get("type") == "CREATE_TRIP" and not trip:
                    action_data = action.get("data", {})

                    start_date_raw = action_data.get("start_date")
                    end_date_raw = action_data.get("end_date")
                    delta = action_data.get("duration_days", 1)  # fallback for backward compat

                    # ✅ Convert strings → date objects RIGHT HERE, once
                    start_date = date.fromisoformat(start_date_raw) if start_date_raw else None
                    end_date = date.fromisoformat(end_date_raw) if end_date_raw else None

                    if start_date and end_date:
                        delta = (end_date - start_date).days + 1

                    # ── أنشئ Trip ─────────────────────────────────────────
                    trip = Trip(
                        trip_id             = str(uuid.uuid4()),
                        user_id             = user_id,
                        destination         = action_data.get("destination", action_data.get("destination_city", "") + ", " + action_data.get("destination_country", "")),
                        start_date          = start_date,
                        end_date            = end_date,
                        number_of_travelers  = action_data.get("traveler_count", action_data.get("number_of_travelers", 1)),
                        budget              = action_data.get("budget", action_data.get("budget_total")),
                    )
                    db.add(trip)
                    await db.flush()

                    # ── أنشئ Itinerary + Days ─────────────────────────────
                    itinerary = Itinerary(
                        itinerary_id = str(uuid.uuid4()),
                        trip_id      = trip.trip_id,
                        title        = f"Trip to {trip.destination}",
                    )
                    db.add(itinerary)
                    await db.flush()

                    if start_date:
                        for i in range(delta):
                            db.add(Day(
                                itinerary_id = itinerary.itinerary_id,
                                day_number   = i + 1,
                                date         = start_date + timedelta(days=i),
                            ))
                    else:
                        for i in range(delta):
                            db.add(Day(
                                itinerary_id = itinerary.itinerary_id,
                                day_number   = i + 1,
                            ))

                    await db.flush()

                    # ── أنشئ Conversation ─────────────────────────────────
                    conversation = Conversation(
                        conversation_id = str(uuid.uuid4()),
                        user_id         = user_id,
                    )
                    db.add(conversation)
                    await db.flush()
                    trip.conversation_id = conversation.conversation_id

                    # ── احفظ كل الرسايل المعلقة ───────────────────────────
                    for msg in pending_messages:
                        db.add(Message(
                            message_id      = str(uuid.uuid4()),
                            conversation_id = conversation.conversation_id,
                            sender          = "user" if msg["role"] == "user" else "agent",
                            content         = msg["content"],
                        ))
                    pending_messages = []

                    await db.commit()

                    # ── بلّغ Flutter ──────────────────────────────────────
                    await manager.send(ws_key, {
                        "type":    "trip_created",
                        "trip_id": trip.trip_id,
                    })

                    # ── حدّث ws_key ──────────────────────────────────────
                    manager.disconnect(ws_key)
                    ws_key = trip.trip_id
                    await manager.connect_existing(ws_key, websocket)

                    break      # ← خرج من loop الـ actions

            # ══════════════════════════════════════════════════════════════
            # نفذ باقي الـ Actions (ADD_ACTIVITY, etc.)
            # ══════════════════════════════════════════════════════════════
            non_create_actions = [a for a in actions if a.get("type") != "CREATE_TRIP"]
            updated_actions    = []

            if trip and non_create_actions:
                updated_actions = await execute_actions(non_create_actions, trip, db)
                await db.commit()

            # ── احفظ رد الـ AI ────────────────────────────────────────────
            pending_messages.append({
                "role":    "assistant",
                "content": full_response,
            })

            if conversation and full_response:
                ai_msg = Message(
                    message_id      = str(uuid.uuid4()),
                    conversation_id = conversation.conversation_id,
                    sender          = "agent",
                    content         = full_response,
                )
                db.add(ai_msg)
                await db.commit()

            # ── بلّغ Flutter لو في تغييرات ────────────────────────────────
            if updated_actions:
                await manager.send(ws_key, {
                    "type": "actions",
                    "data": updated_actions,
                })
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
    auto_msg:  str          = Query(default=None),     # ← Flutter يبعت auto_message هنا
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
        # ── جيب الـ Trip ─────────────────────────────────────────────────
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries)
                .selectinload(Itinerary.days)
                .selectinload(Day.stops),
                selectinload(Trip.conversation),
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
                await process_message(
                    user_text    = auto_msg.strip(),
                    trip         = trip,
                    conversation = conversation,
                    profile_data = profile_data,
                    ws_key       = trip_id,
                    db           = db,
                    user_id      = user_id,
                    token        = token,
                )

        # ── الـ Loop العادي ───────────────────────────────────────────────
        while True:
            data      = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                continue

            async with lock:
                await process_message(
                    user_text    = user_text,
                    trip         = trip,
                    conversation = conversation,
                    profile_data = profile_data,
                    ws_key       = trip_id,
                    db           = db,
                    user_id      = user_id,
                    token        = token,
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
    # Find trip and its linked conversation
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
    # Find trip and its linked conversation
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