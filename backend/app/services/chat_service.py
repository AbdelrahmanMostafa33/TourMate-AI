# backend/app/services/chat_service.py

"""
Chat Service — central orchestrator for chat/conversation DB operations.

Responsible for:
  - Saving messages to the DB Conversation + Message tables
  - Creating conversation records linked to trips
  - Creating trip + itinerary records when the AI generates a plan
  - Retrieving conversation history for AI context
  - Syncing Redis conversation state to DB records

This service decouples the route layer (FastAPI endpoints) from DB logic,
replacing the inline SQLAlchemy code previously in routes/chat.py.
"""

from __future__ import annotations

import uuid
import logging
import datetime
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.chat import Conversation, Message
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day
from app.models.profile import TripProfile
from app.models.enums import ConversationStatus, BudgetLevel, TravelStyle, TripPace
from app.services.itinerary_service import ItineraryService

# Import ConversationState for type annotations in save_state_snapshot.
# Using a TYPE_CHECKING guard to avoid circular imports at runtime.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ai_engine.conversation.conversation_state import ConversationState

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── State Snapshot Operations ─────────────────────────────────────────

    async def save_state_snapshot(
        self,
        conversation_id: str,
        state: "ConversationState",
    ) -> bool:
        """Persist a lightweight snapshot of ConversationState onto the DB Conversation record.

        The snapshot stores enough structured data (phase, slots, turn_count,
        itinerary_id, trip_id) to recover the AI's session context from
        PostgreSQL alone if the Redis data is lost or the TTL expires.

        This is NOT a replacement for Redis — it is a fallback recovery path.
        Redis remains the primary state store for speed and rich object
        fidelity (pool data, message history objects, etc.).

        Args:
            conversation_id: The DB ``Conversation.conversation_id`` to update.
            state:           The in-memory ``ConversationState`` to snapshot.

        Returns:
            True if the snapshot was saved, False on error.
        """
        try:
            # Build a minimal, serializable snapshot — enough to reconstruct
            # the session but without duplicating the full pool data or
            # message history (which is already in the DB).
            snapshot = {
                "phase":               state.phase.value,
                "slots":               state.slots.to_dict(),
                "turn_count":          state.turn_count,
                "itinerary_id":        state.itinerary_id,
                "trip_id":             state.trip_id,
                "last_question_field": state.last_question_field,
                "updated_at":          state.updated_at,
            }

            result = await self.db.execute(
                select(Conversation).where(
                    Conversation.conversation_id == conversation_id
                )
            )
            conv = result.scalar_one_or_none()
            if not conv:
                logger.warning(
                    "[ChatService] Cannot save snapshot: conversation %s not found",
                    conversation_id,
                )
                return False

            # Persist the AI engine session_id on the conversation record
            # so reconnection can attempt a fast Redis lookup before falling
            # back to the state_snapshot recovery path.
            conv.ai_session_id = state.session_id

            conv.state_snapshot = snapshot
            logger.debug(
                "[ChatService] Saved state snapshot for conversation %s (phase=%s, turn=%d)",
                conversation_id, snapshot["phase"], snapshot["turn_count"],
            )
            return True
        except Exception as e:
            logger.warning(
                "[ChatService] Failed to save state snapshot for conversation %s: %s",
                conversation_id, e,
            )
            return False

    # ── Message Operations ────────────────────────────────────────────────

    async def save_message(
        self,
        conversation_id: str,
        sender: str,
        content: str,
        image_data: Optional[str] = None,
        card_data: Optional[dict] = None,
    ) -> Message:
        """Persist a single message to the DB.

        Args:
            conversation_id: FK to the Conversation record.
            sender:           'user' | 'agent'
            content:          Message text.
            image_data:       Optional base64-encoded image data.
            card_data:        Optional structured card data (itinerary, hotel_options,
                              flight_options, booking_data). Persisted so chat history
                              can reconstruct cards exactly as they appeared live.

        Returns:
            The newly created Message ORM object.
        """
        msg = Message(
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            sender=sender,
            content=content,
            image_data=image_data,
            card_data=card_data,
        )
        self.db.add(msg)
        return msg

    async def save_user_message(
        self,
        conversation_id: str,
        content: str,
        image_data: Optional[str] = None,
    ) -> Message:
        """Convenience: save a user message."""
        return await self.save_message(conversation_id, "user", content, image_data=image_data)

    async def save_agent_message(
        self,
        conversation_id: str,
        content: str,
        card_data: Optional[dict] = None,
    ) -> Message:
        """Convenience: save an agent (AI) message with optional structured card data."""
        return await self.save_message(conversation_id, "agent", content, card_data=card_data)

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Load the most recent messages for AI context (oldest first).

        Returns a list of dicts with keys: sender, content.
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))
        return [
            {"sender": m.sender, "content": m.content}
            for m in messages
        ]

    async def conversation_has_messages(self, conversation_id: str) -> bool:
        """Cheap existence check — used to guard against re-processing
        ``auto_msg`` (or any "first message") more than once when a client
        reconnects to the same WebSocket and replays the same query string.

        Returns True as soon as a single message row is found, without
        loading the whole conversation.
        """
        result = await self.db.execute(
            select(Message.message_id)
            .where(Message.conversation_id == conversation_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ── Conversation Operations ───────────────────────────────────────────

    async def get_or_create_conversation(
        self,
        user_id: str,
        trip_id: Optional[str] = None,
    ) -> Conversation:
        """Return an existing conversation linked to ``trip_id``, or create a new one.

        If ``trip_id`` is provided, the method first looks up the trip and
        returns its linked conversation (``Trip.conversation``).  If the trip
        has no conversation yet, a new one is created and linked.

        Without ``trip_id``, a fresh conversation is always created.
        """
        if trip_id:
            result = await self.db.execute(
                select(Trip)
                .options(selectinload(Trip.conversation))
                .where(Trip.trip_id == trip_id)
            )
            trip = result.scalar_one_or_none()
            if trip and trip.conversation:
                return trip.conversation

        conversation = Conversation(
            conversation_id=str(uuid.uuid4()),
            user_id=user_id,
            status=ConversationStatus.active,
        )
        self.db.add(conversation)

        # Link to trip if we found one
        if trip_id and trip:
            trip.conversation_id = conversation.conversation_id

        return conversation

    # ── Trip + Itinerary Creation ─────────────────────────────────────────

    async def create_trip_from_ai_result(
        self,
        user_id: str,
        ai_result: dict,
    ) -> dict:
        """Create a Trip + Conversation + Itinerary + Days from an AI itinerary result.

        This is called when ``handle_chat()`` returns ``response_type == "itinerary"``
        in the new-chat flow (no trip existed yet).

        Args:
            user_id:   Firebase UID.
            ai_result: The full dict returned by ``handle_chat()``.

        Returns:
            A dict with keys:
              - trip_id
              - conversation_id
              - trip (ORM)
              - conversation (ORM)
              - itinerary (ORM)
        """
        itinerary_data = ai_result.get("itinerary", {})
        if not itinerary_data:
            logger.warning(
                "[ChatService] create_trip_from_ai_result called without itinerary data"
            )
            itinerary_data = {}

        # ── Parse temporal fields ─────────────────────────────────────────
        start_date_raw = itinerary_data.get("start_date")
        end_date_raw = itinerary_data.get("end_date")
        duration_days = itinerary_data.get("duration_days")
        if not duration_days:
            duration_days = itinerary_data.get("duration_days", 1)

        start_date: date | None = None
        end_date: date | None = None
        if start_date_raw:
            try:
                start_date = date.fromisoformat(start_date_raw)
            except (ValueError, TypeError):
                logger.warning(
                    "[ChatService] Invalid start_date '%s', ignoring",
                    start_date_raw,
                )
        if end_date_raw:
            try:
                end_date = date.fromisoformat(end_date_raw)
            except (ValueError, TypeError):
                logger.warning(
                    "[ChatService] Invalid end_date '%s', ignoring",
                    end_date_raw,
                )

        if start_date and end_date:
            duration_days = (end_date - start_date).days + 1

        # ── 1. Create Trip ────────────────────────────────────────────────
        destination = (
            itinerary_data.get("destination")
            or itinerary_data.get("destination_city", "")
        )
        # Append country if available
        country = itinerary_data.get("destination_country", "")
        if country and country not in destination:
            destination = f"{destination}, {country}".strip(", ")

        # ── Determine trip_name ───────────────────────────────────────
        trip_name = (
            itinerary_data.get("trip_name")
            or itinerary_data.get("name")
            or itinerary_data.get("title")
            or f"Trip to {destination}"
        )

        trip = Trip(
            trip_id=str(uuid.uuid4()),
            user_id=user_id,
            trip_name=trip_name,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            number_of_travelers=itinerary_data.get(
                "number_of_travelers",
                itinerary_data.get("traveler_count", 1),
            ),
        )
        self.db.add(trip)

        # ── 2. Create Conversation ────────────────────────────────────────
        conversation = Conversation(
            conversation_id=str(uuid.uuid4()),
            user_id=user_id,
            status=ConversationStatus.active,
        )
        self.db.add(conversation)

        # Link trip → conversation
        trip.conversation_id = conversation.conversation_id

        # ── 3. Create Itinerary + Days + Stops ─────────────────────────────
        itinerary = Itinerary(
            itinerary_id=str(uuid.uuid4()),
            trip_id=trip.trip_id,
        )
        self.db.add(itinerary)

        days_data = itinerary_data.get("days", [])
        stops_created = 0

        if days_data:
            has_stops = any(d.get("stops") for d in days_data)

            if has_stops:
                # Delegate to ItineraryService for full day + stop creation
                itin_svc = ItineraryService(self.db)
                stops_created = await itin_svc.create_stops_from_ai_days(
                    itinerary_id=itinerary.itinerary_id,
                    days_data=days_data,
                    accommodation_suggestions=itinerary_data.get("accommodation_suggestions"),
                    start_date=start_date,
                )
                await self.db.flush()
            else:
                # Days present but no stops — create skeleton day records
                for day_data in days_data:
                    day_number = day_data.get("day_number", 1)
                    day_date = None
                    if start_date:
                        day_date = start_date + timedelta(days=day_number - 1)
                    day = Day(
                        itinerary_id=itinerary.itinerary_id,
                        day_number=day_number,
                        date=day_date,
                        theme=day_data.get("theme", ""),
                    )
                    self.db.add(day)
        elif start_date:
            # No day details — create skeleton days from duration
            for i in range(duration_days):
                day = Day(
                    itinerary_id=itinerary.itinerary_id,
                    day_number=i + 1,
                    date=start_date + timedelta(days=i),
                )
                self.db.add(day)

        # ── 4. Create TripProfile from AI profile data ────────────────────────
        profile_data = ai_result.get("profile", {})
        if profile_data:
            profile = TripProfile(
                profile_id=str(uuid.uuid4()),
                trip_id=trip.trip_id,
            )
            # ── Map string values (validate via enums, store as strings) ──
            budget_val = profile_data.get("budget_level")
            if budget_val:
                try:
                    profile.budget_level = BudgetLevel(budget_val)
                except (ValueError, TypeError):
                    profile.budget_level = BudgetLevel.MODERATE.value
                    logger.warning(
                        "[ChatService] Invalid budget_level '%s', defaulting to '%s'",
                        budget_val, profile.budget_level,
                    )

            style_val = profile_data.get("travel_style")
            if style_val:
                try:
                    profile.travel_style = TravelStyle(style_val)
                except (ValueError, TypeError):
                    profile.travel_style = TravelStyle.CULTURAL.value
                    logger.warning(
                        "[ChatService] Invalid travel_style '%s', defaulting to '%s'",
                        style_val, profile.travel_style,
                    )

            pace_val = profile_data.get("pace")
            if pace_val:
                try:
                    profile.pace = TripPace(pace_val)
                except (ValueError, TypeError):
                    # Map legacy AI values (e.g. "moderate") to valid enum values
                    pace_lower = str(pace_val).lower().strip()
                    profile.pace = TripPace.MODERATE.value
                    logger.warning(
                        "[ChatService] Invalid pace '%s', defaulting to '%s'",
                        pace_val, profile.pace,
                    )

            # ── Map list fields ────────────────────────────────────────
            if profile_data.get("interests"):
                profile.interests = profile_data["interests"]
            if profile_data.get("food_preferences"):
                profile.food_preferences = profile_data["food_preferences"]
            if profile_data.get("accommodation_preferences"):
                profile.accommodation_preferences = profile_data["accommodation_preferences"]

            self.db.add(profile)
            logger.info(
                "[ChatService] Created TripProfile %s for trip %s",
                profile.profile_id, trip.trip_id,
            )

        logger.info(
            "[ChatService] Created trip %s / conversation %s for user %s",
            trip.trip_id,
            conversation.conversation_id,
            user_id,
        )

        # ── 5. Save candidate pool + accommodation_suggestions ────────────────
        pool_state = ai_result.get("pool_state") or {}
        accommodations = itinerary_data.get("accommodation_suggestions")
        if pool_state or accommodations:
            combined = dict(pool_state)  # copy so we don't mutate the original
            if accommodations:
                combined["_accommodation_suggestions"] = accommodations
            itin_svc = ItineraryService(self.db)
            await itin_svc.save_candidate_pool(itinerary.itinerary_id, combined)

        return {
            "trip_id": trip.trip_id,
            "conversation_id": conversation.conversation_id,
            "trip": trip,
            "conversation": conversation,
            "itinerary": itinerary,
            "stops_created": stops_created,
        }

    async def save_pool_for_trip(self, trip_id: str, pool_state: dict) -> None:
        """Persist candidate pool JSON on the trip's latest itinerary."""
        if not pool_state:
            return

        result = await self.db.execute(
            select(Itinerary)
            .where(Itinerary.trip_id == trip_id)
            .order_by(Itinerary.created_at.desc())
        )
        itinerary = result.scalars().first()
        if not itinerary:
            return

        itin_svc = ItineraryService(self.db)
        await itin_svc.save_candidate_pool(itinerary.itinerary_id, pool_state)

    async def load_pool_for_trip(self, trip_id: str) -> dict | None:
        """Load persisted candidate pool for edit hydration."""
        itin_svc = ItineraryService(self.db)
        return await itin_svc.get_candidate_pool_by_trip_id(trip_id)

    # ── Redis → DB Sync ──────────────────────────────────────────────────

    async def sync_redis_to_db(
        self,
        conversation_id: str,
        redis_history: list[dict],
    ) -> int:
        """Sync Redis ``ConversationState.history`` messages to the DB ``Message`` table.

        Uses offset-based deduplication instead of content fingerprinting.
        Both Redis history and DB messages are stored in chronological order
        (messages are appended to both at the same time during processing).
        By counting how many DB messages already exist for this conversation,
        we determine the offset into the Redis history that has already been
        synced and only process messages beyond that point.

        This is more robust than ``(sender, content)`` fingerprinting, which
        could lose legitimate duplicate messages (same text from the user in
        separate turns) or mistakenly skip messages whose content happens to
        match an earlier message.

        Args:
            conversation_id: The DB ``Conversation.conversation_id`` to sync into.
            redis_history:   List of message dicts from ``ConversationState.history``
                             (each has ``role``, ``content``, ``timestamp``).

        Returns:
            Number of new messages inserted into the DB.

        Example::

            state = await redis_manager.load(session_id)
            redis_msgs = [m.to_dict() for m in state.history]
            inserted = await svc.sync_redis_to_db(conv_id, redis_msgs)
            await db.commit()
        """
        if not redis_history:
            return 0

        # 1. Count existing DB messages for this conversation.
        #    This gives us the offset into the Redis history that has already
        #    been synced (both are in chronological order).
        result = await self.db.execute(
            select(func.count(Message.message_id))
            .where(Message.conversation_id == conversation_id)
        )
        db_count = result.scalar() or 0

        if db_count >= len(redis_history):
            return 0  # All messages already synced

        # 2. Only process messages beyond the DB count
        new_messages = redis_history[db_count:]
        inserted = 0

        for redis_msg in new_messages:
            role = redis_msg.get("role", "").strip()
            content = redis_msg.get("content", "").strip()

            # Map Redis role to DB sender
            if role == "user":
                sender = "user"
            elif role in ("assistant", "system"):
                sender = "agent"
            else:
                logger.debug(
                    "[ChatService] Skipping Redis message with unknown role '%s'", role
                )
                continue

            if not content:
                continue

            msg = Message(
                message_id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                sender=sender,
                content=content,
            )
            self.db.add(msg)
            inserted += 1

        if inserted > 0:
            logger.info(
                "[ChatService] Synced %d new message(s) to conversation %s "
                "(offset=%d/%d)",
                inserted, conversation_id, db_count, len(redis_history),
            )

        return inserted

    # ── Full History Retrieval ────────────────────────────────────────────

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Retrieve the full message history for a conversation (oldest first).

        This is the canonical history lookup for the AI engine.  Unlike
        ``get_recent_messages()`` (which returns a lightweight ``sender``/
        ``content`` format), this method returns the full message payload
        suitable for building LLM context or serving to the Flutter client.

        Args:
            conversation_id: The DB conversation ID.
            limit:           Max messages to return (default 100).

        Returns:
            List of dicts with keys:
              - message_id
              - conversation_id
              - sender ("user" | "agent")
              - content
              - timestamp (ISO-8601 string)
        """
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
            .limit(limit)
        )
        messages = result.scalars().all()

        # ── Deduplication ────────────────────────────────────────────────
        # Safety net: if a user message and an agent message have the same
        # content in the same conversation, keep only the agent message.
        # This handles lingering duplicates from an earlier bug where
        # ``rebuild_conversation_state_from_db`` incorrectly mapped
        # "agent" (DB) → "user" (ChatMessage role), causing
        # ``sync_redis_to_db`` to insert duplicate user messages.
        seen_content: set[tuple] = set()
        deduped = []
        for m in messages:
            key = (m.sender, m.content)
            if m.sender == "user":
                # Skip user message if the same content exists as agent message
                if ("agent", m.content) not in seen_content:
                    seen_content.add(key)
                    deduped.append(m)
            else:
                if key not in seen_content:
                    seen_content.add(key)
                    deduped.append(m)

        return [
            {
                "message_id": m.message_id,
                "conversation_id": m.conversation_id,
                "sender": m.sender,
                "content": m.content,
                "image_data": m.image_data,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in deduped
        ]

    # ── Conversation Listing ────────────────────────────────────────────

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """Return all conversations for a user, each with the linked trip
        (if any) and the most recent message snippet.

        This powers the ``GET /api/v1/chats/`` endpoint that Flutter uses
        to render the chat sidebar and recent-chats list.

        Returns a list of dicts, each containing:

          - conversation_id
          - trip_id          (str | None)
          - trip             (dict | None) with keys:
                              trip_id, trip_name, destination, status
          - started_at       (ISO-8601 str)
          - last_message     (str | None) – the text of the most recent message
          - last_message_at  (ISO-8601 str | None)
        """
        from sqlalchemy import text

        SQL = text("""
            SELECT
                c.conversation_id,
                t.trip_id         AS trip_id,
                t.trip_name       AS trip_name,
                t.destination     AS destination,
                t.status          AS trip_status,
                c.started_at      AS started_at,
                m.content         AS last_message_content,
                m.timestamp       AS last_message_timestamp
            FROM conversations c
            LEFT JOIN trips t
                ON t.conversation_id = c.conversation_id
            LEFT JOIN LATERAL (
                SELECT content, timestamp
                FROM messages
                WHERE conversation_id = c.conversation_id
                ORDER BY timestamp DESC
                LIMIT 1
            ) m ON TRUE
            WHERE c.user_id = :user_id
            ORDER BY
                COALESCE(m.timestamp, c.started_at) DESC NULLS LAST
            LIMIT :limit
        """)

        result = await self.db.execute(SQL, {"user_id": user_id, "limit": limit})
        rows = result.fetchall()

        out: list[dict] = []
        for row in rows:
            trip_info = None
            if row.trip_id:
                trip_info = {
                    "trip_id":     row.trip_id,
                    "trip_name":   row.trip_name,
                    "destination": row.destination,
                    "status":      row.trip_status,
                }

            started_at_str = (
                row.started_at.isoformat() if row.started_at else None
            )
            last_msg_at_str = (
                row.last_message_timestamp.isoformat()
                if row.last_message_timestamp
                else None
            )

            out.append({
                "conversation_id": row.conversation_id,
                "trip_id":         row.trip_id,
                "trip":            trip_info,
                "created_at":      started_at_str,
                "last_message":    row.last_message_content,
                "last_message_at": last_msg_at_str,
            })

        return out

    # ── Conversation State Rebuild (Redis ← DB) ──────────────────────────

    async def rebuild_conversation_state_from_db(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Optional[dict]:
        """Rebuild a ``ConversationState``-compatible dict from DB records.

        When a user reopens an existing conversation, the Redis
        ``ConversationState`` may have expired (TTL).  This method loads
        the canonical data from PostgreSQL and returns a dict that can be
        used to re-hydrate a ``ConversationState`` in Redis.

        Returns a dict with keys matching ``ConversationState.to_dict()``,
        or ``None`` if the conversation has no meaningful history yet.

        The caller is responsible for saving the returned dict to Redis
        under the correct session key.
        """
        # 1. Load messages from DB (oldest first)
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
        )
        db_messages = result.scalars().all()

        if not db_messages:
            return None  # nothing to rebuild

        # 2. Load the conversation record + linked trip (with eager loading
        #    of itineraries → days → stops to avoid N+1 lazy loads)
        conv_result = await self.db.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.trips)
                .selectinload(Trip.trip_profiles),
                selectinload(Conversation.trips)
                .selectinload(Trip.itineraries)
                .selectinload(Itinerary.days)
                .selectinload(Day.stops),
            )
            .where(Conversation.conversation_id == conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        trip = conversation.trips[0] if conversation and conversation.trips else None

        # 3. Build history list from DB messages
        # IMPORTANT: Map DB sender correctly:
        #   "user"  (DB) → "user"     (ChatMessage role)
        #   "agent" (DB) → "assistant" (ChatMessage role)
        # The OLD mapping (``msg.sender if msg.sender in ("user", "assistant")
        # else "user"``) was WRONG — it left "agent" → "user", which:
        #   1. Confused the AI interpreter (all msgs appeared as user role)
        #   2. Caused ``sync_redis_to_db`` to create DUPLICATE messages (its
        #      ``(sender, content)`` fingerprint saw ("user", "...") from the
        #      rebuilt state, which didn't match ("agent", "...") in the DB).
        from ai_engine.conversation.conversation_state import ChatMessage
        history = []
        for msg in db_messages:
            role = "user" if msg.sender == "user" else "assistant"
            history.append(ChatMessage(
                role=role,
                content=msg.content,
                timestamp=msg.timestamp.isoformat() if msg.timestamp else "",
            ))

        # 4. Determine phase & slots from trip state
        phase = "greeting"
        slots_data = {}
        itinerary_data = None

        if trip:
            # Destination from trip
            if trip.destination:
                city = trip.destination.split(",")[0].strip()
                slots_data["destination_city"] = city
            # Duration from start/end dates
            if trip.start_date and trip.end_date:
                slots_data["duration_days"] = (trip.end_date - trip.start_date).days + 1
            # Group size
            if trip.number_of_travelers:
                slots_data["group_size"] = trip.number_of_travelers

            # Load itinerary data from first itinerary
            if trip.itineraries:
                itinerary = trip.itineraries[0]
                if itinerary.days:
                    from datetime import timedelta
                    days_list = []
                    for day_obj in sorted(itinerary.days, key=lambda d: d.day_number):
                        entry = {
                            "day_number": day_obj.day_number,
                            "theme": day_obj.theme or "",
                            "stops": [],
                        }
                        if day_obj.stops:
                            for stop in sorted(day_obj.stops, key=lambda s: s.order_in_day or 0):
                                snapshot = stop.place_snapshot or {}
                                entry["stops"].append({
                                    "id": stop.stop_id,
                                    "name": snapshot.get("name", ""),
                                    "category": snapshot.get("category", ""),
                                    "suggested_time_of_day": snapshot.get("suggested_time_of_day", ""),
                                    "estimated_duration_minutes": stop.duration_minutes or 60,
                                    "why_recommended": snapshot.get("why_recommended", ""),
                                    "rating": snapshot.get("rating"),
                                    "address": snapshot.get("address", ""),
                                })
                        days_list.append(entry)

                    # Load stops from ItineraryStop relationships
                    # Rebuild accommodation_suggestions from candidate_pool_json
                    # (stored there during create_trip_from_ai_result)
                    pool = itinerary.candidate_pool_json or {}
                    accommodations = pool.get("_accommodation_suggestions", [])

                    itinerary_data = {
                        "destination": trip.destination or "",
                        "days": days_list,
                        "duration_days": slots_data.get("duration_days", len(days_list)),
                        "accommodation_suggestions": accommodations,
                    }

            # TripProfile data
            if trip.trip_profiles:
                profile = trip.trip_profiles[0]
                if profile.budget_level:
                    slots_data["budget_level"] = profile.budget_level
                if profile.travel_style:
                    slots_data["travel_style"] = profile.travel_style
                if profile.pace:
                    slots_data["pace"] = profile.pace
                if profile.interests:
                    slots_data["interests"] = profile.interests
                if profile.food_preferences:
                    slots_data["food_preferences"] = profile.food_preferences
                if profile.accommodation_preferences:
                    slots_data["accommodation_preferences"] = profile.accommodation_preferences

            # Determine phase based on trip status
            if trip.status == "planning":
                phase = "slot_filling"
            elif trip.status in ("itinerary_draft",):
                phase = "itinerary_review"
            elif trip.status in ("awaiting_booking", "booking_pending", "payment_processing"):
                phase = "booking"
            elif trip.status in ("booking_confirmed", "active", "completed"):
                phase = "completed"
            else:
                phase = "itinerary_review" if itinerary_data else "slot_filling"

        # 5. Build the complete state dict
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        state_dict = {
            "session_id": conversation_id,
            "user_id": user_id,
            "phase": phase,
            "slots": slots_data,
            "history": [m.to_dict() for m in history],
            "itinerary": itinerary_data,
            "itinerary_id": None,
            "filtered_places": None,
            "candidate_places": None,
            "pool_metadata": None,
            "trip_id": trip.trip_id if trip else None,
            "created_at": now,
            "updated_at": now,
            "turn_count": len([m for m in history if m.role == "user"]),
            "max_history": 20,
            "last_question_field": None,
            "plan_started_at": None,
        }

        logger.info(
            "[ChatService] Rebuilt ConversationState from DB for conversation %s — "
            "phase=%s, slots=%s, history=%d msgs, trip=%s",
            conversation_id, phase,
            list(slots_data.keys()),
            len(history),
            trip.trip_id if trip else "none",
        )
        return state_dict

    # ── Error Handling ────────────────────────────────────────────────────

    @staticmethod
    def build_error_response(
        message: str = "I ran into an issue processing your request. Please try again.",
        details: Optional[str] = None,
    ) -> dict:
        """Build a safe error response dict when the AI engine fails.

        Replaces the old hardcoded mock fallback data with a clean error
        message that the frontend can display to the user.
        """
        response = {
            "response_type": "error",
            "message": message,
            "itinerary": None,
        }
        if details:
            response["details"] = details
        return response