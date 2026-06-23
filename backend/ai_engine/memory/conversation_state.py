# ai_engine/memory/conversation_state.py

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

    COMPLETED:
        User has approved the itinerary.  The conversation is finished but the
        session is kept alive for a short period in case the user returns.
    """

    GREETING          = "greeting"
    SLOT_FILLING      = "slot_filling"
    PLAN_GENERATION   = "plan_generation"
    ITINERARY_REVIEW  = "itinerary_review"
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
    special_requests:    Optional[str] = None

    # ── Profile Preferences (required) ─────────────────────────────
    budget_level:                   Optional[str] = None   # "budget" | "moderate" | "luxury"
    travel_style:                   Optional[str] = None   # "romantic" | "adventure" | "family" | "solo" | "cultural" | "relaxation"
    pace:                           Optional[str] = None   # "relaxed" | "moderate" | "packed"
    interests:                      Optional[List[str]] = None
    food_preferences:               Optional[List[str]] = None
    accommodation_preferences:      Optional[List[str]] = None

    # ── Smart defaults ────────────────────────────────────────────────
    # Applied automatically when destination + duration are known.
    SMART_DEFAULTS = {
        "group_size": 1,                          # Most common (solo traveler)
        "traveler_group_type": "solo",            # Inferred from 1 traveler
        "budget_level": "moderate",               # Safe middle ground
        "travel_style": "cultural",               # Fits most city destinations
        "pace": "moderate",                       # Most flexible
        "interests": [],                           # Top-rated places fill the day
        "food_preferences": ["local cuisine"],    # Works everywhere
        "accommodation_preferences": ["hotel"],   # Most general
        "travel_dates": "",                       # Handled as optional in pipeline
    }

    def missing_required(self) -> List[str]:
        """Return the list of REQUIRED fields that are still None.

        Only destination + duration are truly mandatory.
        Everything else gets smart defaults via ``fill_defaults()``.
        """
        missing: List[str] = []
        if not self.destination_city:
            missing.append("destination")
        if self.duration_days is None:
            missing.append("duration")
        return missing

    def is_complete(self) -> bool:
        """True when all required slots are filled.

        Only checks destination + duration (the true minimum).
        Non-mandatory fields get smart defaults via ``fill_defaults()``.
        """
        return len(self.missing_required()) == 0

    def fill_defaults(self) -> None:
        """Fill any unset non-mandatory fields with smart defaults.

        Call this right before triggering itinerary generation
        when only destination + duration have been collected.
        """
        # Infer traveler group type from group_size
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

        # Fill remaining defaults
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
        """Serialize to a plain dict (JSON-safe)."""
        d = asdict(self)
        # Convert None-int to None (already handled by Optional[int])
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TripSlots":
        """Deserialize from a dict (e.g. loaded from Redis)."""
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
        """
        Merge fields extracted from the intent parser into the slots.

        Only overwrites fields that are present (not None) in *intent*.
        This lets us accumulate information across multiple turns.
        """
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

        # Accumulate list fields (append, don't overwrite)
        for list_field in ("interests", "food_preferences", "accommodation_preferences"):
            new_values = intent.get(list_field)
            if new_values and isinstance(new_values, list):
                existing = getattr(self, list_field) or []
                combined = list(existing)
                for v in new_values:
                    if v not in combined:
                        combined.append(v)
                setattr(self, list_field, combined)

        # Backward compat: accumulate interests from special_requests
        if not self.interests and intent.get("special_requests"):
            self.interests = [intent["special_requests"]]


# ── Message History Entry ─────────────────────────────────────────────────────

@dataclass
class ChatMessage:
    """A single message in the conversation history."""

    role:      str        # "user" | "assistant" | "system"
    content:   str
    timestamp: str = ""   # ISO-8601 UTC string
    metadata:  Optional[Dict[str, Any]] = None  # e.g. {"intent_type": "plan_trip"}

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

    Attributes:
        session_id:   Unique ID for this session (UUID4).
        user_id:      Firebase UID.
        phase:        Current ConversationPhase.
        slots:        TripSlots accumulated from user messages.
        history:      Rolling window of ChatMessage objects.
        itinerary:    The current itinerary dict (set after PLAN_GENERATION).
        itinerary_id: Database ID of the saved trip (set after approval).
        created_at:   ISO-8601 timestamp of session creation.
        updated_at:   ISO-8601 timestamp of last update.
        turn_count:   Number of user messages in this session.
        max_history:  Maximum messages to keep in the rolling window.
    """

    session_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:      str = ""
    phase:        ConversationPhase = ConversationPhase.GREETING
    slots:        TripSlots = field(default_factory=TripSlots)
    history:      List[ChatMessage] = field(default_factory=list)
    itinerary:    Optional[Dict[str, Any]] = None
    itinerary_id: Optional[str] = None
    candidate_places: Optional[List[Dict[str, Any]]] = None  # places from last pipeline run, for modifier agent
    created_at:   str = ""
    updated_at:   str = ""
    turn_count:   int = 0
    max_history:  int = 20
    last_question_field: Optional[str] = None  # which slot was last asked about (e.g. 'pace', 'budget_level')
    plan_started_at: Optional[str] = None  # ISO-8601 timestamp when PLAN_GENERATION started (for timeout detection)

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full state to a JSON-safe dict."""
        return {
            "session_id":   self.session_id,
            "user_id":      self.user_id,
            "phase":        self.phase.value,
            "slots":        self.slots.to_dict(),
            "history":      [m.to_dict() for m in self.history],
            "itinerary":    self.itinerary,
            "itinerary_id": self.itinerary_id,
            "candidate_places": self.candidate_places,
            "created_at":   self.created_at,
            "updated_at":   self.updated_at,
            "turn_count":   self.turn_count,
            "max_history":  self.max_history,
            "last_question_field": self.last_question_field,
            "plan_started_at": self.plan_started_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Deserialize from a dict loaded from Redis."""
        return cls(
            session_id   = data.get("session_id", str(uuid.uuid4())),
            user_id      = data.get("user_id", ""),
            phase        = ConversationPhase(data.get("phase", ConversationPhase.GREETING.value)),
            slots        = TripSlots.from_dict(data.get("slots", {})),
            history      = [ChatMessage.from_dict(m) for m in data.get("history", [])],
            itinerary    = data.get("itinerary"),
            itinerary_id = data.get("itinerary_id"),
            candidate_places = data.get("candidate_places"),
            created_at   = data.get("created_at", ""),
            updated_at   = data.get("updated_at", ""),
            turn_count   = data.get("turn_count", 0),
            max_history  = data.get("max_history", 20),
            last_question_field = data.get("last_question_field"),
            plan_started_at = data.get("plan_started_at"),
        )

    # ── Mutations ────────────────────────────────────────────────────────────

    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Append a user message to the history and bump the turn counter."""
        self.history.append(ChatMessage(role="user", content=content, metadata=metadata))
        self.turn_count += 1
        self._trim_history()
        self._touch()

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Append an assistant message to the history."""
        self.history.append(ChatMessage(role="assistant", content=content, metadata=metadata))
        self._trim_history()
        self._touch()

    def add_system_message(self, content: str) -> None:
        """Append a system message (e.g. tool result, error notification)."""
        self.history.append(ChatMessage(role="system", content=content))
        self._trim_history()
        self._touch()

    def transition_to(self, new_phase: ConversationPhase) -> None:
        """Move to a new conversation phase."""
        self.phase = new_phase
        self._touch()

    def set_itinerary(self, itinerary: Dict[str, Any], candidate_places: Optional[List[Dict[str, Any]]] = None) -> None:
        """Store the generated itinerary and move to ITINERARY_REVIEW."""
        self.itinerary = itinerary
        self.plan_started_at = None
        if candidate_places is not None:
            self.candidate_places = candidate_places
        self.transition_to(ConversationPhase.ITINERARY_REVIEW)

    def approve_itinerary(self, itinerary_id: str) -> None:
        """Mark the itinerary as approved."""
        self.itinerary_id = itinerary_id
        self.transition_to(ConversationPhase.COMPLETED)

    def reset_for_new_trip(self) -> None:
        """Reset the state to start collecting a new trip (keeps session_id)."""
        self.phase = ConversationPhase.SLOT_FILLING
        self.slots = TripSlots()
        self.itinerary = None
        self.itinerary_id = None
        self.candidate_places = None
        self.turn_count = 0
        self.last_question_field = None
        self.plan_started_at = None
        self.history.clear()
        self._touch()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_system_context(self) -> str:
        """
        Build a context string summarising the conversation so far.

        This is injected into the LLM system prompt so it knows the
        conversation history without re-parsing every message.
        """
        lines = [
            f"Conversation Phase: {self.phase.value}",
            f"Turn: {self.turn_count}",
        ]

        # Include collected trip slots
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
            lines.append(f"Special requests: {self.slots.special_requests}")

        # Include collected profile preferences
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

        # Include recent history (last 5 messages for context)
        recent = self.history[-5:]
        if recent:
            lines.append("\nRecent messages:")
            for msg in recent:
                lines.append(f"  [{msg.role}] {msg.content[:100]}")

        return "\n".join(lines)

    def _trim_history(self) -> None:
        """Keep only the last *max_history* messages."""
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def _touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
