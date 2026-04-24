# app/models/user.py

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    user_id    = Column(String, primary_key=True)
    full_name  = Column(String)
    email      = Column(String, unique=True)
    phone      = Column(String)
    role       = Column(String, default="user")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)

    # ✅ Relationship to Profile
    profile = relationship("UserProfile", back_populates="user", uselist=False)