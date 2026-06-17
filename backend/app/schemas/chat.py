from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.enums import ConversationStatus


# ─── Enums ───────────────────────────────────────────────────────────────────

class SenderType(str, Enum):
    """Matches Message.sender field: 'user' | 'agent'."""
    user  = "user"
    agent = "agent"


# ─── Message ─────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    """Create schema for Message – aligns with model fields."""
    sender:  SenderType
    content: str


class MessageResponse(BaseModel):
    """Response schema for Message – aligns with model fields."""
    message_id:      str
    conversation_id: str
    sender:          str          # "user" | "agent"
    content:         str
    timestamp:       datetime

    class Config:
        from_attributes = True


# ─── Conversation ────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    """Create schema for Conversation – user_id derived from auth."""
    trip_id: str


class ConversationResponse(BaseModel):
    """Response schema for Conversation – aligns with model fields."""
    conversation_id: str
    trip_id:         str
    user_id:         str
    started_at:      datetime
    status:          ConversationStatus
    messages:        List[MessageResponse] = []

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Summary schema for Conversation – aligns with model fields."""
    conversation_id: str
    trip_id:         str
    started_at:      datetime
    status:          ConversationStatus

    class Config:
        from_attributes = True


# ─── Chat (service-level DTOs) ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    trip_id: Optional[str] = None