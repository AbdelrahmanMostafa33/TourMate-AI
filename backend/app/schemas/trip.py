from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime, time
from enum import Enum

class TripStatus(str, Enum):
    planning  = "planning"
    active    = "active"
    completed = "completed"

class InputMode(str, Enum):
    ai_chat = "ai_chat"
    manual  = "manual"

class ActivityType(str, Enum):
    attraction = "attraction"
    hotel      = "hotel"
    restaurant = "restaurant"
    transport  = "transport"
    
class ActivityCreate(BaseModel):
    name:           str
    type:           ActivityType
    time:           Optional[time]  = None  # type: ignore
    duration_hours: Optional[float] = None
    notes:          Optional[str]   = None

class ActivityResponse(ActivityCreate):
    activity_id: int
    day_id:      int
    created_at:  datetime

    class Config:
        from_attributes = True


class TripDayCreate(BaseModel):
    day_number: int
    date:       Optional[date] = None # type: ignore
    activities: Optional[List[ActivityCreate]] = []

class TripDayResponse(BaseModel):
    day_id:     int
    trip_id:    str
    day_number: int
    date:       Optional[date]
    activities: List[ActivityResponse] = []

    class Config:
        from_attributes = True
        
class TripCreate(BaseModel):
    destination_city:    str
    destination_country: str
    start_date:          Optional[date]
    end_date:            Optional[date]
    duration_days:       Optional[int]   = 1
    budget_total:        Optional[float] = None
    traveler_count:      Optional[int]   = 1
    input_mode:          Optional[InputMode] = InputMode.ai_chat

class TripResponse(BaseModel):
    trip_id:             str
    user_id:             str
    destination_city:    str
    destination_country: str
    start_date:          date
    end_date:            date
    duration_days:       int
    status:              TripStatus
    budget_total:        Optional[float]
    traveler_count:      int
    input_mode:          InputMode
    created_at:          datetime
    days:                List[TripDayResponse] = []

    class Config:
        from_attributes = True

class TripSummary(BaseModel):

    trip_id:             str
    destination_city:    str
    destination_country: str
    start_date:          date
    end_date:            date
    duration_days:       int
    status:              TripStatus

    class Config:
        from_attributes = True

class TripStatusUpdate(BaseModel):
    status: TripStatus

