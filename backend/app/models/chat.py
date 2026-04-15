from sqlalchemy import (
    Column, String, Integer, Float, Numeric,
    Date, DateTime, Time, Text, Enum, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
 
from app.core.database import Base
# ─── Conversation ─────────────────────────────────────────────────────────────
 
class Conversation(Base):
    __tablename__ = "conversations"
 
    conversation_id = Column(String, primary_key=True)
    trip_id         = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id         = Column(String, ForeignKey("users.id"),     nullable=False, index=True)
    created_at      = Column(DateTime, default=func.now())
 
    # Relationships
    trip     = relationship("Trip",    back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
 
 
# ─── Message ──────────────────────────────────────────────────────────────────
 
class Message(Base):
    __tablename__ = "messages"
 
    message_id      = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    role            = Column(Enum(MessageRole), nullable=False)
    content         = Column(Text, nullable=False)
    actions         = Column(JSON, nullable=True)   # e.g. [{"type": "ADD_ACTIVITY", "data": {...}}]
    created_at      = Column(DateTime, default=func.now())
 
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
