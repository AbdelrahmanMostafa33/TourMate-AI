"""Quiz model."""

from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    quiz_id      = Column(String, primary_key=True)
    user_id      = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    answers      = Column(JSON, nullable=True)  # Map<String, String>
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")
