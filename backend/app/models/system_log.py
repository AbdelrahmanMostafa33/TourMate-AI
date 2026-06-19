"""EventLog model – matches ERD event_log table."""

from sqlalchemy import (
    Column, String, Text, DateTime, JSON,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class EventLog(Base):
    __tablename__ = "event_log"

    log_id      = Column(String, primary_key=True)
    user_id     = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    trip_id     = Column(String, ForeignKey("trips.trip_id"), nullable=True, index=True)
    event_type  = Column(String, nullable=False)
    event_data  = Column(JSON, nullable=True)
    created_at  = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User")
    trip = relationship("Trip")
