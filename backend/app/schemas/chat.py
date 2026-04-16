from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime, time
from enum import Enum
from schemas.trip import TripResponse


class MessageRole(str, Enum):
    user      = "user"
    assistant = "assistant"

class MessageCreate(BaseModel):
    role:    MessageRole
    content: str
    actions: Optional[List[Any]] = None  # [{"type": "ADD_ACTIVITY", "data": {...}}]

class MessageResponse(MessageCreate):
    message_id:      str
    conversation_id: str
    created_at:      datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    trip_id: str

class ConversationResponse(BaseModel):
    conversation_id: str
    trip_id:         str
    user_id:         str
    created_at:      datetime
    messages:        List[MessageResponse] = []

    class Config:
        from_attributes = True

class ConversationSummary(BaseModel):

    conversation_id: str
    trip_id:         str
    created_at:      datetime

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message:  str
    trip_id:  Optional[str] = None  # None = رحلة جديدة


class MessageResponse(BaseModel):
    message_id: str
    role:       str
    content:    str
    actions:    Optional[List[Any]] = None

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    trip_id:          str
    message:          str
    itinerary:        Optional[TripResponse] = None