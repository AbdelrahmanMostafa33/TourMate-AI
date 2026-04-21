from pydantic import BaseModel
from typing import Optional, List
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


# ─── Activity ────────────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    name:           str
    type:           ActivityType
    location_name:  Optional[str]   = None
    latitude:       Optional[float] = None
    longitude:      Optional[float] = None
    order_in_day:   Optional[int]   = None
    time:           Optional[time]  = None
    duration_hours: Optional[float] = None
    notes:          Optional[str]   = None

class ActivityResponse(BaseModel):
    activity_id:    int
    day_id:         int
    name:           str
    type:           ActivityType
    time:           Optional[time]   = None
    duration_hours: Optional[float]  = None
    notes:          Optional[str]    = None
    order_in_day:   Optional[int]    = None
    location_name:  Optional[str]    = None
    lat:            Optional[float]  = None
    lng:            Optional[float]  = None
    created_at:     datetime

    class Config:
        from_attributes = True


# ─── TripDay ─────────────────────────────────────────────────────────────────

class TripDayCreate(BaseModel):
    day_number: int
    date:       Optional[date] = None
    activities: Optional[List[ActivityCreate]] = []

class TripDayResponse(BaseModel):
    day_id:     int
    trip_id:    str
    day_number: int
    date:       date | None
    activities: List[ActivityResponse] = []

    class Config:
        from_attributes = True


# ─── Trip ────────────────────────────────────────────────────────────────────

class TripCreate(BaseModel):
    destination_city:    str
    destination_country: str
    start_date:          Optional[date]
    end_date:            Optional[date]
    budget_total:        Optional[float]    = None
    traveler_count:      Optional[int]      = 1
    input_mode:          Optional[InputMode] = InputMode.ai_chat
    preferences:         Optional[str]      = None      

class TripResponse(BaseModel):
    trip_id:             str
    user_id:             str
    destination_city:    str
    destination_country: str
    start_date:          Optional[date]
    end_date:            Optional[date]
    duration_days:       int
    status:              TripStatus
    budget_total:        Optional[float] = None
    traveler_count:      int
    input_mode:          InputMode
    created_at:          datetime
    days:                List[TripDayResponse] = []
    auto_message:        Optional[str]  = None          

    class Config:
        from_attributes = True


class TripSummary(BaseModel):
    trip_id:             str
    destination_city:    str
    destination_country: str
    start_date:          Optional[date]
    end_date:            Optional[date]
    duration_days:       int
    status:              TripStatus

    class Config:
        from_attributes = True

class TripStatusUpdate(BaseModel):
    status: TripStatus