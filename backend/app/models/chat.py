"""Conversation and Message models - matches the class diagram."""

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ConversationStatus


# --- Conversation ---

class Conversation(Base):
    """Conversation model – ERD: trips optionally references conversations via conversation_id FK."""
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True)
    user_id         = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    started_at      = Column(DateTime, default=func.now())
    status          = Column(
        SAEnum(ConversationStatus, name="conversation_status"),
        default=ConversationStatus.active,
        nullable=False,
    )

    # Relationships
    user     = relationship("User",    back_populates="conversations")
    trips    = relationship("Trip",    back_populates="conversation")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


# --- Message ---

class Message(Base):
    __tablename__ = "messages"

    message_id      = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    sender          = Column(String, nullable=False)            # "user" | "agent"
    content         = Column(Text, nullable=False)
    image_data      = Column(Text, nullable=True)               # Base64-encoded image for user-uploaded photos
    timestamp       = Column(DateTime, default=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
