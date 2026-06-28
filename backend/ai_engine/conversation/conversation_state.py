# ai_engine/conversation/conversation_state.py

"""
ConversationState: session-level state for multi-turn trip planning conversations.

Tracks the conversation phase, collected trip slots, message history, and the
current itinerary being discussed.  Persisted to Redis via SessionManager so
the state survives WebSocket reconnections and server restarts.

Phase lifecycle:
    GREETING → SLOT_FILLING → PLAN_GENERATION → ITINERARY_REVIEW → COMPLETED
                                          ↑                         │
                                          └───── (user requests edits)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Conversation Phases ───────────────────────────────────────────────────────

class ConversationPhase(str, Enum):
    """
    Represents the current stage of a multi-turn conversation.

    GREETING:
        User just connected. Bot says hello, asks if they want to plan a trip.

    SLOT_FILLING:
        Bot is collecting required trip information (destination, duration, dates,
        group size, special requests) through natural back-and-forth.

    PLAN_GENERATION:
        All required slots collected.  The LangGraph pipeline is running to
        produce an itinerary.  (Async — may take several seconds.)

    ITINERARY_REVIEW:
        Itinerary has been generated and presented to the user.  The user can
        approve, request changes, or ask questions about the plan.

    HOTEL_SELECTION:
        User approved the stops but needs to choose a hotel.  The system has
        presented 2-3 hotel options and is waiting for the user's selection.

    COMPLETED:
        User has approved the itinerary.  The conversation is finished but the
        session is kept alive for a short period in case the user returns.
    """

    GREETING          = "greeting"
    SLOT_FILLING      = "slot_filling"
    PLAN_GENERATION   = "plan_generation"
    ITINERARY_REVIEW  = "itinerary_review"
    HOTEL_SELECTION   = "hotel_selection"
    COMPLETED         = "completed"


# ── Trip Slots ────────────────────────────────────────────────────────────────

@dataclass
class TripSlots:
    """
    Trip information collected from the user during slot-filling.

    Required fields (must be non-None before PLAN_GENERATION):
        - destination_city, duration_days
        - budget_level, travel_style, pace
        - interests, food_preferences, accommodation_preferences

    Optional fields (enrich the plan but are not blocking):
        - destination_country, travel_dates, group_size, special_requests
    """

    # ── Trip Info ──────────────────────────────────────────────────
    destination_city:    Optional[str] = None
    destination_country: Optional[str] = None
    duration_days:       Optional[int] = None
    travel_dates:        Optional[str] = None        # "June 15-20, 2026" or "next summer"
    group_size:          Optional[int] = None         # number of travelers
    traveler_group_type: Optional[str] = None          # "solo" | "couple" | "family" | "friends" | "business"
    special_requests:    Optional[List[str]] = None

    # ── Profile Preferences (required) ─────────────────────────────
    budget_level:                   Optional[str] = None   # "budget" | "moderate" | "luxury"
    travel_style:                   Optional[str] = None   # "romantic" | "adventure" | "family" | "solo" | "cultural" | "relaxation"
    pace:                           Optional[str] = None   # "relaxed" | "moderate" | "packed"
    interests:                      Optional[List[str]] = None
    food_preferences:               Optional[List[str]] = None
    accommodation_preferences:      Optional[List[str]] = None

    # ── Smart defaults ────────────────────────────────────────────────
    SMART_DEFAULTS = {
        "group_size": 1,
        "traveler_group_type": "solo",
        "budget_level": "moderate",
        "travel_style": "cultural",
        "pace": "moderate",
        "interests": [],
        "food_preferences": ["local cuisine"],
        "accommodation_preferences": ["hotel"],
        "travel_dates": "",
    }

    def missing_required(self) -> List[str]:
        """Return the list of REQUIRED fields that are still None."""
        missing: List[str] = []
        if not self.destination_city:
            missing.append("city")
        if self.duration_days is None:
            missing.append("duration")
        # Interests are ALWAYS required before planning.
        # Users can provide interests by typing them, uploading an image,
        # or explicitly opting out (interests=[] means "no preference").
        if self.interests is None:
            missing.append("interests")
        return missing

    def is_complete(self) -> bool:
        """True when all required slots are filled."""
        return len(self.missing_required()) == 0

    def fill_defaults(self) -> None:
        """Fill any unset non-mandatory fields with smart defaults."""
        if self.group_size is None:
            self.group_size = self.SMART_DEFAULTS["group_size"]
        if not self.traveler_group_type:
            if self.group_size == 1:
                self.traveler_group_type = "solo"
            elif self.group_size == 2:
                self.traveler_group_type = "couple"
            elif self.group_size >= 3:
                self.traveler_group_type = "friends"
            else:
                self.traveler_group_type = self.SMART_DEFAULTS["traveler_group_type"]

        if not self.budget_level:
            self.budget_level = self.SMART_DEFAULTS["budget_level"]
        if not self.travel_style:
            self.travel_style = self.SMART_DEFAULTS["travel_style"]
        if not self.pace:
            self.pace = self.SMART_DEFAULTS["pace"]
        if not self.interests:
            self.interests = list(self.SMART_DEFAULTS["interests"])
        if not self.food_preferences:
            self.food_preferences = list(self.SMART_DEFAULTS["food_preferences"])
        if not self.accommodation_preferences:
            self.accommodation_preferences = list(self.SMART_DEFAULTS["accommodation_preferences"])
        if not self.travel_dates:
            self.travel_dates = self.SMART_DEFAULTS["travel_dates"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TripSlots":
        return cls(
            destination_city       = data.get("destination_city"),
            destination_country    = data.get("destination_country"),
            duration_days          = data.get("duration_days"),
            travel_dates           = data.get("travel_dates"),
            group_size             = data.get("group_size"),
            traveler_group_type    = data.get("traveler_group_type"),
            special_requests       = data.get("special_requests"),
            budget_level           = data.get("budget_level"),
            travel_style           = data.get("travel_style"),
            pace                   = data.get("pace"),
            interests              = data.get("interests"),
            food_preferences       = data.get("food_preferences"),
            accommodation_preferences = data.get("accommodation_preferences"),
        )

    def merge(self, intent: Dict[str, Any]) -> None:
        """Merge fields extracted from the intent parser into the slots."""
        field_map = {
            "destination_city":       "destination_city",
            "destination_country":    "destination_country",
            "duration_days":          "duration_days",
            "travel_dates":           "travel_dates",
            "group_size":             "group_size",
            "traveler_group_type":    "traveler_group_type",
            "special_requests":       "special_requests",
            "budget_level":           "budget_level",
            "travel_style":           "travel_style",
            "pace":                   "pace",
        }
        for intent_key, slot_key in field_map.items():
            value = intent.get(intent_key)
            if value is not None:
                setattr(self, slot_key, value)

        for list_field in ("interests", "food_preferences", "accommodation_preferences"):
            new_values = intent.get(list_field)
            if new_values is not None and isinstance(new_values, list):
                if new_values:
                    # Merge non-empty list into existing (union, no duplicates)
                    existing = getattr(self, list_field) or []
                    combined = list(existing)
                    for v in new_values:
                        if v not in combined:
                            combined.append(v)
                    setattr(self, list_field, combined)
                # Ignore empty lists from the LLM — they are often default
                # values from structured output, not intentional opt-outs.
                # The explicit opt-out case is handled upstream by the LLM
                # choosing plan_trip + fill_defaults().

        if not self.interests and intent.get("special_requests"):
            raw = intent["special_requests"]
            if isinstance(raw, list):
                self.interests = list(raw)
            else:
                self.interests = [raw]


# ── Message History Entry ─────────────────────────────────────────────────────

@dataclass
class ChatMessage:
    """A single message in the conversation history."""

    role:      str        # "user" | "assistant" | "system"
    content:   str
    timestamp: str = ""   # ISO-8601 UTC string
    metadata:  Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("metadata") is None:
            del d["metadata"]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            role      = data["role"],
            content   = data["content"],
            timestamp = data.get("timestamp", ""),
            metadata  = data.get("metadata"),
        )


# ── ConversationState ─────────────────────────────────────────────────────────

@dataclass
class ConversationState:
    """
    Complete session state for a multi-turn conversation.

    This is the single source of truth for the conversation.  The
    SessionManager serializes/deserializes this to/from Redis as JSON.
    """

    session_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:      str = ""
    phase:        ConversationPhase = ConversationPhase.GREETING
    slots:        TripSlots = field(default_factory=TripSlots)
    history:      List[ChatMessage] = field(default_factory=list)
    itinerary:    Optional[Dict[str, Any]] = None
    itinerary_id: Optional[str] = None
    filtered_places: Optional[List[Dict[str, Any]]] = None
    candidate_places: Optional[List[Dict[str, Any]]] = None
    pool_metadata: Optional[Dict[str, Any]] = None
    trip_id: Optional[str] = None
    created_at:   str = ""
    updated_at:   str = ""
    turn_count:   int = 0
    max_history:  int = 20
    last_question_field: Optional[str] = None
    plan_started_at: Optional[str] = None

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id":   self.session_id,
            "user_id":      self.user_id,
            "phase":        self.phase.value,
            "slots":        self.slots.to_dict(),
            "history":      [m.to_dict() for m in self.history],
            "itinerary":    self.itinerary,
            "itinerary_id": self.itinerary_id,
            "filtered_places": self.filtered_places,
            "candidate_places": self.candidate_places,
            "pool_metadata": self.pool_metadata,
            "trip_id": self.trip_id,
            "created_at":   self.created_at,
            "updated_at":   self.updated_at,
            "turn_count":   self.turn_count,
            "max_history":  self.max_history,
            "last_question_field": self.last_question_field,
            "plan_started_at": self.plan_started_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        return cls(
            session_id   = data.get("session_id", str(uuid.uuid4())),
            user_id      = data.get("user_id", ""),
            phase        = ConversationPhase(data.get("phase", ConversationPhase.GREETING.value)),
            slots        = TripSlots.from_dict(data.get("slots", {})),
            history      = [ChatMessage.from_dict(m) for m in data.get("history", [])],
            itinerary    = data.get("itinerary"),
            itinerary_id = data.get("itinerary_id"),
            filtered_places = data.get("filtered_places"),
            candidate_places = data.get("candidate_places"),
            pool_metadata = data.get("pool_metadata"),
            trip_id = data.get("trip_id"),
            created_at   = data.get("created_at", ""),
            updated_at   = data.get("updated_at", ""),
            turn_count   = data.get("turn_count", 0),
            max_history  = data.get("max_history", 20),
            last_question_field = data.get("last_question_field"),
            plan_started_at = data.get("plan_started_at"),
        )

    # ── Mutations ────────────────────────────────────────────────────────────

    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.history.append(ChatMessage(role="user", content=content, metadata=metadata))
        self.turn_count += 1
        self._trim_history()
        self._touch()

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.history.append(ChatMessage(role="assistant", content=content, metadata=metadata))
        self._trim_history()
        self._touch()

    def add_system_message(self, content: str) -> None:
        self.history.append(ChatMessage(role="system", content=content))
        self._trim_history()
        self._touch()

    def transition_to(self, new_phase: ConversationPhase) -> None:
        self.phase = new_phase
        self._touch()

    def set_itinerary(
        self,
        itinerary: Dict[str, Any],
        candidate_places: Optional[List[Dict[str, Any]]] = None,
        filtered_places: Optional[List[Dict[str, Any]]] = None,
        pool_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from ai_engine.services.pool_manager import compute_pool_metadata

        self.itinerary = itinerary
        self.plan_started_at = None
        if filtered_places is not None:
            self.filtered_places = filtered_places
        if candidate_places is not None:
            self.candidate_places = candidate_places
        if pool_metadata is not None:
            self.pool_metadata = pool_metadata
        elif self.filtered_places or self.candidate_places:
            self.pool_metadata = compute_pool_metadata(
                self.filtered_places,
                self.candidate_places,
                self.itinerary,
            )
        self.transition_to(ConversationPhase.ITINERARY_REVIEW)

    def get_pool_state(self) -> Dict[str, Any]:
        """Return a serializable snapshot of the candidate pool for persistence."""
        from ai_engine.services.pool_manager import build_pool_state_dict

        return build_pool_state_dict(
            self.filtered_places,
            self.candidate_places,
            self.itinerary,
        )

    def hydrate_pool(self, pool_state: Dict[str, Any]) -> None:
        """Restore pool fields from Redis or PostgreSQL."""
        if not pool_state:
            return
        self.filtered_places = pool_state.get("filtered_places") or self.filtered_places
        self.candidate_places = pool_state.get("candidate_places") or self.candidate_places
        self.pool_metadata = pool_state.get("pool_metadata") or self.pool_metadata

    def approve_itinerary(self, itinerary_id: str) -> None:
        self.itinerary_id = itinerary_id
        self.transition_to(ConversationPhase.COMPLETED)

    def reset_for_new_trip(self) -> None:
        self.phase = ConversationPhase.SLOT_FILLING
        self.slots = TripSlots()
        self.itinerary = None
        self.itinerary_id = None
        self.filtered_places = None
        self.candidate_places = None
        self.pool_metadata = None
        self.trip_id = None
        self.turn_count = 0
        self.last_question_field = None
        self.plan_started_at = None
        self.history.clear()
        self._touch()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_system_context(self) -> str:
        lines = [
            f"Conversation Phase: {self.phase.value}",
            f"Turn: {self.turn_count}",
        ]
        if self.slots.destination_city:
            lines.append(f"Destination: {self.slots.destination_city}")
        if self.slots.destination_country:
            lines.append(f"Country: {self.slots.destination_country}")
        if self.slots.duration_days:
            lines.append(f"Duration: {self.slots.duration_days} days")
        if self.slots.travel_dates:
            lines.append(f"Dates: {self.slots.travel_dates}")
        if self.slots.group_size:
            lines.append(f"Group size: {self.slots.group_size}")
        if self.slots.traveler_group_type:
            lines.append(f"Traveler group: {self.slots.traveler_group_type}")
        if self.slots.special_requests:
            sr = self.slots.special_requests
            if isinstance(sr, list):
                lines.append(f"Special requests: {', '.join(sr)}")
            else:
                lines.append(f"Special requests: {sr}")
        if self.slots.budget_level:
            lines.append(f"Budget: {self.slots.budget_level}")
        if self.slots.travel_style:
            lines.append(f"Style: {self.slots.travel_style}")
        if self.slots.pace:
            lines.append(f"Pace: {self.slots.pace}")
        if self.slots.interests:
            lines.append(f"Interests: {', '.join(self.slots.interests)}")
        if self.slots.food_preferences:
            lines.append(f"Food: {', '.join(self.slots.food_preferences)}")
        if self.slots.accommodation_preferences:
            lines.append(f"Accommodation: {', '.join(self.slots.accommodation_preferences)}")

        recent = self.history[-5:]
        if recent:
            lines.append("\nRecent messages:")
            for msg in recent:
                lines.append(f"  [{msg.role}] {msg.content[:100]}")

        return "\n".join(lines)

    def _trim_history(self) -> None:
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
