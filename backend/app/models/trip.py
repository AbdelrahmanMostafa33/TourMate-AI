from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, Enum, Text
from sqlalchemy.sql import func
from app.core.database import Base

class Trip(Base):
    __tablename__ = "trips"

    trip_id = Column(String, primary_key=True)
    user_id = Column(String)
    destination_city = Column(String)
    destination_country = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    duration_days = Column(Integer)
    status = Column(Enum("pending", "generated", "approved", "cancelled", name="trip_status"), default="pending")
    approved_at = Column(DateTime)
    budget_total = Column(Numeric)
    traveler_count = Column(Integer)
    input_mode = Column(Enum("text", "image", "both", name="input_mode"))
    user_input = Column(Text)
    created_at = Column(DateTime, default=func.now())