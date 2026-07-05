"""Versioned chat protocol shared by the WebSocket and history APIs.

The backend is the source of truth for UI structure.  Natural-language text
travels as text segments; cards/widgets travel as typed card segments.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


CHAT_PROTOCOL = "tourmate.chat"
CHAT_PROTOCOL_VERSION = 1


class ChatEventType(str, Enum):
    RESPONSE_STARTED = "assistant.response.started"
    TEXT_DELTA = "assistant.text.delta"
    CARD = "chat.card"
    RESPONSE_COMPLETED = "assistant.response.completed"
    PROGRESS = "pipeline.progress"
    PHASE = "conversation.phase"
    TRIP_CREATED = "trip.created"
    TRIP_APPROVED = "trip.approved"
    ACTIONS_APPLIED = "actions.applied"
    ITINERARY_UPDATED = "itinerary.updated"
    ERROR = "chat.error"


class ChatCardType(str, Enum):
    ITINERARY = "itinerary"
    HOTEL_OPTIONS = "hotel_options"
    FLIGHT_OPTIONS = "flight_options"
    BOOKING = "booking"
    IMAGE_FEATURES = "image_features"


class TextSegment(BaseModel):
    type: Literal["text"] = "text"
    text: str


class CardSegment(BaseModel):
    type: Literal["card"] = "card"
    card_type: ChatCardType
    data: dict[str, Any]


class ChatHistoryPayload(BaseModel):
    protocol: Literal["tourmate.chat"] = CHAT_PROTOCOL
    version: Literal[1] = CHAT_PROTOCOL_VERSION
    segments: list[TextSegment | CardSegment] = Field(default_factory=list)
    auxiliary: dict[str, Any] = Field(default_factory=dict)


class ChatEnvelope(BaseModel):
    protocol: Literal["tourmate.chat"] = CHAT_PROTOCOL
    version: Literal[1] = CHAT_PROTOCOL_VERSION
    type: ChatEventType
    sequence: int
    response_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class TextDeltaData(BaseModel):
    text: str


class CardEventData(BaseModel):
    card_type: ChatCardType
    data: dict[str, Any]
    presentation: Literal["append", "replace"] = "append"


class ResponseCompletedData(BaseModel):
    status: Literal["ok", "error"] = "ok"
    message: str = ""
    segments: list[TextSegment | CardSegment] = Field(default_factory=list)


class ProgressData(BaseModel):
    agent: str = ""
    status: Literal["running", "done", "error"] = "running"
    message: str = ""


class PhaseData(BaseModel):
    phase: str


class TripCreatedData(BaseModel):
    trip_id: str
    itinerary_id: str | None = None


class ErrorData(BaseModel):
    message: str
    details: str | None = None


class ActionsData(BaseModel):
    actions: list[dict[str, Any]] = Field(default_factory=list)


_EVENT_DATA_MODELS: dict[ChatEventType, type[BaseModel] | None] = {
    ChatEventType.RESPONSE_STARTED: None,
    ChatEventType.TEXT_DELTA: TextDeltaData,
    ChatEventType.CARD: CardEventData,
    ChatEventType.RESPONSE_COMPLETED: ResponseCompletedData,
    ChatEventType.PROGRESS: ProgressData,
    ChatEventType.PHASE: PhaseData,
    ChatEventType.TRIP_CREATED: TripCreatedData,
    ChatEventType.TRIP_APPROVED: None,
    ChatEventType.ACTIONS_APPLIED: ActionsData,
    ChatEventType.ITINERARY_UPDATED: None,
    ChatEventType.ERROR: ErrorData,
}


def build_event(
    event_type: ChatEventType,
    *,
    sequence: int,
    response_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and serialize a WebSocket event envelope."""
    data = data or {}
    data_model = _EVENT_DATA_MODELS[event_type]
    if data_model is not None:
        data = data_model.model_validate(data).model_dump(mode="json", exclude_none=True)

    return ChatEnvelope(
        type=event_type,
        sequence=sequence,
        response_id=response_id,
        data=data,
    ).model_dump(mode="json", exclude_none=True)


def text_segment(text: str) -> dict[str, Any]:
    return TextSegment(text=text).model_dump(mode="json")


def card_segment(card_type: ChatCardType | str, data: dict[str, Any]) -> dict[str, Any]:
    return CardSegment(card_type=ChatCardType(card_type), data=data).model_dump(mode="json")


def build_history_payload(
    *,
    text: str,
    cards: list[dict[str, Any]],
    auxiliary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical structured payload stored in Message.card_data."""
    segments: list[dict[str, Any]] = []
    if text:
        segments.append(text_segment(text))
    for card in cards:
        segments.append(card_segment(card["card_type"], card["data"]))

    return ChatHistoryPayload(
        segments=segments,
        auxiliary=auxiliary or {},
    ).model_dump(mode="json", exclude_none=True)
