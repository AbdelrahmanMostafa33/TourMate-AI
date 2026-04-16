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
    location_name:  Optional[str]   = None   # ← جديد
    latitude:       Optional[float] = None   # ← جديد (الخريطة)
    longitude:      Optional[float] = None   # ← جديد (الخريطة)
    order_in_day:   Optional[int]   = None   # ← جديد (الترتيب)
    time:           Optional[time]  = None # type: ignore
    duration_hours: Optional[float] = None
    notes:          Optional[str]   = None

class ActivityResponse(BaseModel):
    activity_id:    int
    name:           str
    type:           ActivityType
    time:           Optional[time]   = None # type: ignore
    duration_hours: Optional[float]  = None
    notes:          Optional[str]    = None
    order_in_day:   Optional[int]    = None
    location_name:  Optional[str]    = None
    lat:            Optional[float]  = None
    lng:            Optional[float]  = None

    class Config:
        from_attributes = True



class TripDayCreate(BaseModel):
    day_number: int
    date:       Optional[date] = None # type: ignore
    activities: Optional[List[ActivityCreate]] = []

class DayResponse(BaseModel):
    day_id:     int
    day_number: int
    date:       Optional[date] = None # type: ignore
    activities: List[ActivityResponse] = []

    class Config:
        from_attributes = True
        
class TripCreate(BaseModel):
    user_id:             str             # ← جديد (مؤقت، بعدين هيجي من JWT)
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
    destination_city:    str
    destination_country: str
    status:              str
    duration_days:       int
    days:                List[DayResponse] = []

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

