from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime, time

from app.models.enums import TripStatus, ItineraryStatus, StopStatus, TravelMode


# ─── ItineraryStop ───────────────────────────────────────────────────────────

class StopCreate(BaseModel):
    """Create schema for ItineraryStop – aligns with model fields."""
    place_id:               Optional[str]  = None
    place_snapshot:         Optional[dict] = None
    scheduled_time:         Optional[time] = None
    duration_minutes:       Optional[int]  = None
    order_in_day:           Optional[int]  = 0
    minutes_from_prev_stop: Optional[int]  = None
    travel_mode:            Optional[TravelMode] = None
    estimated_cost:         Optional[float] = None
    ai_notes:               Optional[str]   = None
    user_notes:             Optional[str]   = None
    status:                 Optional[StopStatus] = StopStatus.planned


class StopResponse(BaseModel):
    """Response schema for ItineraryStop – aligns with model fields."""
    stop_id:                int
    day_id:                 int
    place_id:               Optional[str]  = None
    place_snapshot:         Optional[dict] = None
    scheduled_time:         Optional[time] = None
    duration_minutes:       Optional[int]  = None
    order_in_day:           Optional[int]  = None
    minutes_from_prev_stop: Optional[int]  = None
    travel_mode:            Optional[TravelMode] = None
    estimated_cost:         Optional[float] = None
    ai_notes:               Optional[str]   = None
    user_notes:             Optional[str]   = None
    status:                 StopStatus
    created_at:             datetime

    class Config:
        from_attributes = True


# ─── Day ─────────────────────────────────────────────────────────────────────

class DayCreate(BaseModel):
    """Create schema for Day – aligns with model fields."""
    day_number:     int
    date:           Optional[date] = None
    theme:          Optional[str]  = None
    description:    Optional[str]  = None
    estimated_cost: Optional[float] = None
    stops:          Optional[List[StopCreate]] = []


class DayResponse(BaseModel):
    """Response schema for Day – aligns with model fields."""
    day_id:         int
    itinerary_id:   str
    day_number:     int
    date:           Optional[date]
    theme:          Optional[str]   = None
    description:    Optional[str]   = None
    estimated_cost: Optional[float] = None
    stops:          List[StopResponse] = []

    class Config:
        from_attributes = True


# ─── Itinerary ───────────────────────────────────────────────────────────────

class ItineraryCreate(BaseModel):
    """Create schema for Itinerary – aligns with model fields."""
    title:               Optional[str]  = None
    description:         Optional[str]  = None
    total_estimated_cost: Optional[float] = None
    days:                Optional[List[DayCreate]] = []


class ItineraryResponse(BaseModel):
    """Response schema for Itinerary – aligns with model fields."""
    itinerary_id:         str
    trip_id:              str
    version_number:       int
    title:                Optional[str]   = None
    description:          Optional[str]   = None
    total_estimated_cost: Optional[float] = None
    status:               ItineraryStatus
    created_at:           datetime
    updated_at:           datetime
    days:                 List[DayResponse] = []

    class Config:
        from_attributes = True


# ─── Trip ────────────────────────────────────────────────────────────────────

class TripCreate(BaseModel):
    """Create schema for Trip – aligns with model fields."""
    destination:           str
    trip_name:             Optional[str]   = None
    start_date:            Optional[date]  = None
    end_date:              Optional[date]  = None
    number_of_travelers:   Optional[int]   = 1
    budget:                Optional[float] = None
    preferences:           Optional[List[str]] = None


class TripResponse(BaseModel):
    """Response schema for Trip – aligns with model fields.
    Also includes optional fields injected by routes (auto_message, conversation_id).
    """
    trip_id:              str
    user_id:              str
    trip_name:            Optional[str]   = None
    destination:          str
    start_date:           Optional[date]
    end_date:             Optional[date]
    number_of_travelers:  int
    budget:               Optional[float]  = None
    preferences:          Optional[List[str]] = None
    status:               TripStatus
    created_at:           datetime
    itineraries:          List[ItineraryResponse] = []
    # Injected by routes
    auto_message:         Optional[str] = None
    conversation_id:      Optional[str] = None

    class Config:
        from_attributes = True


class TripSummary(BaseModel):
    """Summary schema for Trip – aligns with model fields."""
    trip_id:              str
    trip_name:            Optional[str]   = None
    destination:          str
    start_date:           Optional[date]
    end_date:             Optional[date]
    number_of_travelers:  int
    status:               TripStatus

    class Config:
        from_attributes = True


class TripStatusUpdate(BaseModel):
    status: TripStatus