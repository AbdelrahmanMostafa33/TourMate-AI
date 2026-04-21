from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
import uuid

from app.core.database import get_db
from app.core.firebase import verify_token          # ← مباشرةً من firebase
from app.core.security import get_current_user
from app.models.trip import Trip, TripDay, TripActivity
from app.models.chat import Conversation, Message, MessageRole
from app.models.profile import UserProfile
from app.ws.manager import manager

router = APIRouter()


# ─── Helper: صورة الرحلة الحالية للـ AI ───────────────────────────────────────

def build_trip_snapshot(trip: Trip) -> dict:
    return {
        "trip_id":             trip.trip_id,
        "destination_city":    trip.destination_city,
        "destination_country": trip.destination_country,
        "duration_days":       trip.duration_days,
        "days": [
            {
                "day_id":     day.day_id,
                "day_number": day.day_number,
                "date":       str(day.date) if day.date else None,
                "activities": [
                    {
                        "activity_id":    act.activity_id,
                        "name":           act.name,
                        "type":           act.type,
                        "time":           str(act.time) if act.time else None,
                        "duration_hours": act.duration_hours,
                        "notes":          act.notes,
                        "order_in_day":   act.order_in_day,
                        "location_name":  act.location_name,
                        "lat":            act.lat,
                        "lng":            act.lng,
                    }
                    for act in day.activities
                ],
            }
            for day in trip.days
        ],
    }


# ─── Helper: نفذ الـ actions على الـ DB ──────────────────────────────────────

async def execute_actions(actions: list, trip: Trip, db: AsyncSession) -> list:
    updated_actions = []

    for action in actions:
        action_type = action.get("type")
        data        = action.get("data", {})

        # ── ADD_DAY ──────────────────────────────────────────────────────────
        if action_type == "ADD_DAY":
            day_number = data.get("day_number", 1)
            existing   = next(
                (d for d in trip.days if d.day_number == day_number), None
            )
            if not existing:
                new_day = TripDay(
                    trip_id    = trip.trip_id,
                    day_number = day_number,
                    date       = data.get("date"),
                )
                db.add(new_day)
                await db.flush()
                action["generated_id"] = new_day.day_id

        # ── ADD_ACTIVITY ─────────────────────────────────────────────────────
        elif action_type == "ADD_ACTIVITY":
            day_number = data.get("day_number", 1)
            day        = next(
                (d for d in trip.days if d.day_number == day_number), None
            )
            if not day:
                day = TripDay(trip_id=trip.trip_id, day_number=day_number)
                db.add(day)
                await db.flush()

            new_activity = TripActivity(
                day_id         = day.day_id,
                name           = data.get("name", ""),
                type           = data.get("type", "attraction"),
                time           = data.get("time"),
                duration_hours = data.get("duration_hours"),
                notes          = data.get("notes"),
                order_in_day   = data.get("order_in_day", 0),
                location_name  = data.get("location_name"),
                lat            = data.get("lat"),
                lng            = data.get("lng"),
            )
            db.add(new_activity)
            await db.flush()
            action["generated_id"] = new_activity.activity_id

        # ── UPDATE_ACTIVITY ← جديد ───────────────────────────────────────────
        elif action_type == "UPDATE_ACTIVITY":
            activity_id = data.get("activity_id")
            if activity_id:
                result = await db.execute(
                    select(TripActivity).where(
                        TripActivity.activity_id == activity_id
                    )
                )
                act = result.scalar_one_or_none()
                if act:
                    if data.get("name"):           act.name           = data["name"]
                    if data.get("time"):           act.time           = data["time"]
                    if data.get("notes"):          act.notes          = data["notes"]
                    if data.get("duration_hours"): act.duration_hours = data["duration_hours"]
                    if data.get("location_name"):  act.location_name  = data["location_name"]
                    if data.get("lat"):            act.lat            = data["lat"]
                    if data.get("lng"):            act.lng            = data["lng"]
                    if data.get("order_in_day") is not None:
                        act.order_in_day = data["order_in_day"]
                    await db.flush()

        # ── DELETE_ACTIVITY ──────────────────────────────────────────────────
        elif action_type == "DELETE_ACTIVITY":
            activity_id = data.get("activity_id")
            if activity_id:
                await db.execute(
                    delete(TripActivity).where(
                        TripActivity.activity_id == activity_id
                    )
                )

        # ── UPDATE_TRIP ──────────────────────────────────────────────────────
        elif action_type == "UPDATE_TRIP":
            if data.get("destination_city"):
                trip.destination_city    = data["destination_city"]
            if data.get("destination_country"):
                trip.destination_country = data["destination_country"]
            if data.get("duration_days"):
                trip.duration_days       = data["duration_days"]
            if data.get("budget_total"):
                trip.budget_total        = data["budget_total"]
            await db.flush()

        updated_actions.append(action)

    return updated_actions


# ─── Helper: جيب أو أنشئ Conversation ────────────────────────────────────────

async def get_or_create_conversation(
    trip_id: str,
    user_id: str,
    db:      AsyncSession,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(Conversation.trip_id == trip_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            conversation_id = str(uuid.uuid4()),
            trip_id         = trip_id,
            user_id         = user_id,
        )
        db.add(conversation)
        await db.flush()

    return conversation


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

    await manager.connect(ws_key, websocket)       # ← manager يعمل accept

    try:
        # ── جيب الـ Profile ──────────────────────────────────────────────
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile      = profile_result.scalar_one_or_none()
        profile_data = {}
        if profile:
            profile_data = {
                "persona_name":       profile.persona_name,
                "interests":          profile.interests,
                "budget_level":       profile.budget_level,
                "adventure_relaxing": profile.adventure_relaxing,
                "travel_companion":   profile.travel_companion,
            }

        # ── State ────────────────────────────────────────────────────────
        trip_id         = None
        conversation_id = None
        history_list    = []
        pending_messages = []      # ← رسايل قبل إنشاء الـ Trip

        while True:
            data      = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                continue

            # ── احفظ الرسالة مؤقتاً ─────────────────────────────────────
            pending_messages.append({
                "role":    "user",
                "content": user_text,
            })

            # ── لو Trip موجود، احفظ في DB ───────────────────────────────
            if conversation_id:
                user_msg = Message(
                    message_id      = str(uuid.uuid4()),
                    conversation_id = conversation_id,
                    role            = MessageRole.user,
                    content         = user_text,
                )
                db.add(user_msg)
                await db.commit()

            # ── typing ───────────────────────────────────────────────────
            await manager.send(ws_key, {"type": "typing"})

            # ── كلم الـ AI ───────────────────────────────────────────────
            full_response = ""
            actions       = []

            try:
                from ai.chat.chat_handler import handle_message_stream
                async for chunk in handle_message_stream({
                    "message":      user_text,
                    "user_profile": profile_data,
                    "history":      history_list,
                    "trip_data":    None,
                }):
                    if chunk["type"] == "text":
                        full_response += chunk["content"]
                        await manager.send(ws_key, {
                            "type": "token",
                            "data": chunk["content"],
                        })
                    elif chunk["type"] == "actions":
                        actions = chunk["data"]

            except Exception:
                full_response = "تمام! جاري تجهيز الرحلة... (AI placeholder)"
                for token_chunk in full_response.split():
                    await manager.send(ws_key, {
                        "type": "token",
                        "data": token_chunk + " ",
                    })

            await manager.send(ws_key, {"type": "done"})

            # ── شوف لو فيه CREATE_TRIP ───────────────────────────────────
            for action in actions:
                if action.get("type") == "CREATE_TRIP":
                    action_data = action.get("data", {})

                    from datetime import date, timedelta

                    start_date = action_data.get("start_date")
                    end_date   = action_data.get("end_date")
                    delta      = 1
                    if start_date and end_date:
                        delta = (
                            date.fromisoformat(end_date) -
                            date.fromisoformat(start_date)
                        ).days + 1

                    # ── أنشئ الـ Trip ─────────────────────────────────────
                    new_trip = Trip(
                        trip_id             = str(uuid.uuid4()),
                        user_id             = user_id,
                        destination_city    = action_data.get("destination_city", ""),
                        destination_country = action_data.get("destination_country", ""),
                        start_date          = start_date,
                        end_date            = end_date,
                        duration_days       = delta,
                        budget_total        = action_data.get("budget_total"),
                        traveler_count      = action_data.get("traveler_count", 1),
                    )
                    db.add(new_trip)
                    await db.flush()

                    # ── أنشئ TripDays ─────────────────────────────────────
                    if start_date:
                        for i in range(delta):
                            db.add(TripDay(
                                trip_id    = new_trip.trip_id,
                                day_number = i + 1,
                                date       = date.fromisoformat(start_date) + timedelta(days=i),
                            ))

                    # ── أنشئ Conversation ─────────────────────────────────
                    new_conv = Conversation(
                        conversation_id = str(uuid.uuid4()),
                        trip_id         = new_trip.trip_id,
                        user_id         = user_id,
                    )
                    db.add(new_conv)
                    await db.flush()

                    trip_id         = new_trip.trip_id
                    conversation_id = new_conv.conversation_id

                    # ── احفظ كل الرسايل القديمة ──────────────────────────
                    for msg in pending_messages:
                        db.add(Message(
                            message_id      = str(uuid.uuid4()),
                            conversation_id = conversation_id,
                            role            = MessageRole.user if msg["role"] == "user" else MessageRole.assistant,
                            content         = msg["content"],
                        ))

                    pending_messages = []    # ← فرّغها

                    await db.commit()

                    # ── بلّغ Flutter ──────────────────────────────────────
                    await manager.send(ws_key, {
                        "type":    "trip_created",
                        "trip_id": trip_id,
                    })

                    # ── حدّث الـ manager key ──────────────────────────────
                    manager.disconnect(ws_key)
                    ws_key = trip_id
                    await manager.connect_existing(ws_key, websocket)

            # ── احفظ رد الـ AI ────────────────────────────────────────────
            pending_messages.append({
                "role":    "assistant",
                "content": full_response,
            })

            if conversation_id and full_response:
                ai_msg = Message(
                    message_id      = str(uuid.uuid4()),
                    conversation_id = conversation_id,
                    role            = MessageRole.assistant,
                    content         = full_response,
                    actions         = actions if actions else None,
                )
                db.add(ai_msg)
                await db.commit()

            # ── حدّث الـ history ──────────────────────────────────────────
            history_list.append({"role": "user",      "content": user_text})
            history_list.append({"role": "assistant", "content": full_response})
            if len(history_list) > 20:
                history_list = history_list[-20:]

    except WebSocketDisconnect:
        manager.disconnect(ws_key)
# ═══════════════════════════════════════════════════════════════════════════════
# WS /ws/chat/{trip_id}?token=<firebase_token>
# ═══════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws/chat/{trip_id}")
async def websocket_chat(
    trip_id:   str,
    websocket: WebSocket,
    token:     str          = Query(...),          # ← Firebase token كـ query param
    db:        AsyncSession = Depends(get_db),
):
    # ── Auth: تحقق من الـ token قبل أي حاجة ─────────────────────────────────
    user = verify_token(token)
    if not user:
        await websocket.close(code=4001)           # 4001 = Unauthorized
        return

    user_id = user["uid"]

    await manager.connect(trip_id, websocket)
    lock = manager.get_lock(trip_id)

    try:
        # ── جيب الـ Trip وتأكد إن اليوزر صاحبها ─────────────────────────────
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.days)
                .selectinload(TripDay.activities)
            )
            .where(
                Trip.trip_id == trip_id,
                Trip.user_id == user_id,            # ← ownership check
            )
        )
        trip = result.scalar_one_or_none()
        if not trip:
            await manager.send(trip_id, {"type": "error", "data": "Trip not found"})
            await websocket.close(code=4004)
            return

        # ── جيب أو أنشئ Conversation ─────────────────────────────────────────
        conversation = await get_or_create_conversation(trip_id, user_id, db)
        await db.commit()

        while True:
            # ── استقبل رسالة من الموبايل ─────────────────────────────────────
            data      = await websocket.receive_json()
            user_text = data.get("message", "").strip()
            if not user_text:
                continue

            # ── احفظ رسالة اليوزر ────────────────────────────────────────────
            user_msg = Message(
                message_id      = str(uuid.uuid4()),
                conversation_id = conversation.conversation_id,
                role            = MessageRole.user,
                content         = user_text,
            )
            db.add(user_msg)
            await db.commit()

            # ── Lock: منع رسالتين يتعالجوا في نفس الوقت ─────────────────────
            async with lock:

                # ── جيب آخر 10 رسايل كـ context ─────────────────────────────
                history_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation.conversation_id)
                    .order_by(Message.created_at.desc())
                    .limit(10)
                )
                history_list = [
                    {"role": m.role.value, "content": m.content}
                    for m in reversed(history_result.scalars().all())
                ]

                # ── جيب الـ UserProfile ───────────────────────────────────────
                profile_result = await db.execute(
                    select(UserProfile).where(UserProfile.user_id == user_id)
                )
                profile      = profile_result.scalar_one_or_none()
                profile_data = {}
                if profile:
                    profile_data = {
                        "persona_name":       profile.persona_name,
                        "interests":          profile.interests,
                        "budget_level":       profile.budget_level,
                        "adventure_relaxing": profile.adventure_relaxing,
                        "travel_companion":   profile.travel_companion,
                    }

                # ── جيب الـ trip snapshot ─────────────────────────────────────
                await db.refresh(trip)
                trip_snapshot = build_trip_snapshot(trip)

                # ── بعت "typing" للموبايل ─────────────────────────────────────
                await manager.send(trip_id, {"type": "typing"})

                # ── كلم الـ AI (Streaming) ────────────────────────────────────
                full_response = ""
                actions       = []

                try:
                    from ai.chat.chat_handler import handle_message_stream
                    async for chunk in handle_message_stream({
                        "message":      user_text,
                        "user_profile": profile_data,
                        "history":      history_list,
                        "trip_data":    trip_snapshot,
                    }):
                        if chunk["type"] == "text":
                            full_response += chunk["content"]
                            await manager.send(trip_id, {
                                "type": "token",
                                "data": chunk["content"],
                            })
                        elif chunk["type"] == "actions":
                            actions = chunk["data"]

                except Exception:
                    # Placeholder لحد ما الـ AI Team يخلصوا
                    full_response = "تمام! جاري تجهيز الرحلة... (AI placeholder)"
                    for token_chunk in full_response.split():
                        await manager.send(trip_id, {
                            "type": "token",
                            "data": token_chunk + " ",
                        })

                # ── بعت "done" ───────────────────────────────────────────────
                await manager.send(trip_id, {"type": "done", "data": None})

                # ── نفذ الـ actions على الـ DB ────────────────────────────────
                await db.refresh(trip)
                updated_actions = await execute_actions(actions, trip, db)

                # ── احفظ رد الـ AI ────────────────────────────────────────────
                ai_msg = Message(
                    message_id      = str(uuid.uuid4()),
                    conversation_id = conversation.conversation_id,
                    role            = MessageRole.assistant,
                    content         = full_response,
                    actions         = updated_actions if updated_actions else None,
                )
                db.add(ai_msg)
                await db.commit()

                # ── لو فيه أماكن جديدة، بعت إشارة للخريطة ───────────────────
                if updated_actions:
                    await manager.send(trip_id, {
                        "type": "actions",
                        "data": updated_actions,
                    })
                    await manager.send(trip_id, {"type": "itinerary_updated"})

    except WebSocketDisconnect:
        manager.disconnect(trip_id)
        
#-------------------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════════
# GET /chat/{trip_id}/history
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/chat/{trip_id}/history")
async def get_history(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.trip_id == trip_id,
            Conversation.user_id == current_user["uid"],
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = sorted(conversation.messages, key=lambda m: m.created_at)
    return [
        {
            "message_id": m.message_id,
            "role":       m.role.value,
            "content":    m.content,
            "actions":    m.actions,
            "created_at": m.created_at,
        }
        for m in messages
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /chat/{trip_id}/clear
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/chat/{trip_id}/clear")
async def clear_chat(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.trip_id == trip_id,
            Conversation.user_id == current_user["uid"],
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.execute(
        delete(Message).where(
            Message.conversation_id == conversation.conversation_id
        )
    )
    await db.commit()
    return {"message": "Chat cleared successfully"}
