from pydantic import BaseModel
from typing import Optional
from datetime import date

class TripCreate(BaseModel):
    destination_city: str
    destination_country: str
    start_date: date
    end_date: date
    budget_total: Optional[float] = None
    traveler_count: Optional[int] = 1
    user_input: Optional[str] = None

class TripResponse(BaseModel):
    trip_id: str
    destination_city: str
    destination_country: str
    start_date: date
    end_date: date
    duration_days: int
    status: str

    class Config:
        from_attributes = True