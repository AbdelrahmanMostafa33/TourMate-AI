from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

from app.models.enums import TripStatus, ItineraryStatus, StopStatus, TravelMode, TimeOfDay


# ─── ItineraryStop ───────────────────────────────────────────────────────────

class StopCreate(BaseModel):
    """Create schema for ItineraryStop – aligns with model fields."""
    place_id:               Optional[str]  = None
    place_snapshot:         Optional[dict] = None
    duration_minutes:       Optional[int]  = None
    order_in_day:           Optional[int]  = 0
    time_of_day:            Optional[TimeOfDay] = None
    minutes_from_prev_stop: Optional[int]  = None
    travel_mode:            Optional[TravelMode] = None
    estimated_cost:         Optional[float] = None
    ai_notes:               Optional[str]   = None
    status:                 Optional[StopStatus] = StopStatus.planned


class StopResponse(BaseModel):
    """Response schema for ItineraryStop – aligns with model fields."""
    stop_id:                str
    day_id:                 str
    place_id:               Optional[str]  = None
    place_snapshot:         Optional[dict] = None
    duration_minutes:       Optional[int]  = None
    order_in_day:           Optional[int]  = None
    time_of_day:            Optional[TimeOfDay] = None
    minutes_from_prev_stop: Optional[int]  = None
    travel_mode:            Optional[TravelMode] = None
    estimated_cost:         Optional[float] = None
    ai_notes:               Optional[str]   = None
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
    stops:          Optional[List[StopCreate]] = []


class DayResponse(BaseModel):
    """Response schema for Day – aligns with model fields."""
    day_id:         str
    itinerary_id:   str
    day_number:     int
    date:           Optional[date]
    theme:          Optional[str]   = None
    description:    Optional[str]   = None
    stops:          List[StopResponse] = []

    class Config:
        from_attributes = True


# ─── Itinerary ───────────────────────────────────────────────────────────────

class ItineraryCreate(BaseModel):
    """Create schema for Itinerary – aligns with model fields."""
    description:         Optional[str]  = None
    days:                Optional[List[DayCreate]] = []


class ItineraryResponse(BaseModel):
    """Response schema for Itinerary – aligns with model fields."""
    itinerary_id:         str
    trip_id:              str
    version_number:       int
    description:          Optional[str]   = None
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


class TripResponse(BaseModel):
    """Response schema for Trip – aligns with model fields."""
    trip_id:              str
    user_id:              str
    trip_name:            Optional[str]   = None
    destination:          str
    start_date:           Optional[date]
    end_date:             Optional[date]
    number_of_travelers:  int
    conversation_id:      Optional[str]   = None
    status:               TripStatus
    created_at:           datetime
    updated_at:           Optional[datetime] = None
    approved_at:          Optional[datetime] = None
    itineraries:          List[ItineraryResponse] = []
    # Injected by routes
    auto_message:              Optional[str] = None
    pending_bookings_count:    int          = 0

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
    duration:             Optional[int]   = None

    class Config:
        from_attributes = True


class TripStatusUpdate(BaseModel):
    status: TripStatus