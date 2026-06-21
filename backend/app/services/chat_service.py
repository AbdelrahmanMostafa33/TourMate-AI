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
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.chat import Conversation, Message
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day
from app.models.enums import ConversationStatus
from app.services.itinerary_service import ItineraryService

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Message Operations ────────────────────────────────────────────────

    async def save_message(
        self,
        conversation_id: str,
        sender: str,
        content: str,
    ) -> Message:
        """Persist a single message to the DB.

        Args:
            conversation_id: FK to the Conversation record.
            sender:           'user' | 'agent'
            content:          Message text.

        Returns:
            The newly created Message ORM object.
        """
        msg = Message(
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            sender=sender,
            content=content,
        )
        self.db.add(msg)
        return msg

    async def save_user_message(
        self,
        conversation_id: str,
        content: str,
    ) -> Message:
        """Convenience: save a user message."""
        return await self.save_message(conversation_id, "user", content)

    async def save_agent_message(
        self,
        conversation_id: str,
        content: str,
    ) -> Message:
        """Convenience: save an agent (AI) message."""
        return await self.save_message(conversation_id, "agent", content)

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

        trip = Trip(
            trip_id=str(uuid.uuid4()),
            user_id=user_id,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            number_of_travelers=itinerary_data.get(
                "number_of_travelers",
                itinerary_data.get("traveler_count", 1),
            ),
            budget=itinerary_data.get("budget", itinerary_data.get("budget_total")),
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

        logger.info(
            "[ChatService] Created trip %s / conversation %s for user %s",
            trip.trip_id,
            conversation.conversation_id,
            user_id,
        )

        return {
            "trip_id": trip.trip_id,
            "conversation_id": conversation.conversation_id,
            "trip": trip,
            "conversation": conversation,
            "itinerary": itinerary,
            "stops_created": stops_created,
        }

    # ── Redis → DB Sync ──────────────────────────────────────────────────

    async def sync_redis_to_db(
        self,
        conversation_id: str,
        redis_history: list[dict],
    ) -> int:
        """Sync Redis ``ConversationState.history`` messages to the DB ``Message`` table.

        Compares the provided Redis message list against existing DB messages
        for the conversation and inserts any that are not yet persisted.

        Deduplication is based on ``(sender, content)`` only — NOT timestamp.

        NOTE: An earlier version of this method fingerprinted on
        ``(sender, content, minute_precision_timestamp)``. That worked for
        true "same instant" duplicates, but failed to catch duplicates
        produced by a full re-processing of the same message minutes apart
        (e.g. a client reconnecting and replaying ``auto_msg`` after the
        socket dropped) — the new copy would land in a different minute
        bucket and look "new". Since ``save_user_message`` /
        ``save_agent_message`` already persist messages directly during
        normal processing, this sync is a secondary safety net whose job is
        to catch anything Redis has that the DB doesn't — and an exact
        (sender, content) match for that purpose is virtually always a true
        duplicate, not a coincidence, so we drop timestamp from the key.

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

        # 1. Load existing DB messages for this conversation
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
        )
        existing = result.scalars().all()

        # Build a set of fingerprints for fast dedup.
        # Fingerprint = (sender, content) — see docstring for why timestamp
        # was dropped from the key.
        existing_fingerprints: set[tuple] = set()
        for msg in existing:
            existing_fingerprints.add((msg.sender, msg.content))

        # 2. Map Redis ChatMessage → DB Message, skipping duplicates
        #    Redis roles:    "user", "assistant", "system"
        #    DB senders:     "user", "agent"
        inserted = 0
        for redis_msg in redis_history:
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

            fingerprint = (sender, content)

            if fingerprint in existing_fingerprints:
                continue  # Already exists in DB

            # Insert new message
            msg = Message(
                message_id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                sender=sender,
                content=content,
            )
            self.db.add(msg)
            existing_fingerprints.add(fingerprint)
            inserted += 1

        if inserted > 0:
            logger.info(
                "[ChatService] Synced %d new message(s) to conversation %s",
                inserted, conversation_id,
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

        return [
            {
                "message_id": m.message_id,
                "conversation_id": m.conversation_id,
                "sender": m.sender,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in messages
        ]

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