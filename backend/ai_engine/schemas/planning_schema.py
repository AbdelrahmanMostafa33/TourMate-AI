"""
Pydantic models for structured itinerary output from the Planning Agent.

Using ``.with_structured_output()`` guarantees valid JSON with all required
keys (including ``days``), eliminating manual JSON extraction and repair.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AccommodationSuggestion(BaseModel):
    """A hotel recommendation for the trip."""

    id: str = Field(description="Unique place identifier")
    name: str = Field(description="Hotel name")
    sub_category: str = Field(default="", description="Sub-category, e.g. 'hotel', 'resort'")
    accommodation_type: str = Field(default="", description="Type: 'hotel', 'hostel', 'resort', 'luxury'")
    lat: float = Field(default=0.0, description="Latitude")
    lon: float = Field(default=0.0, description="Longitude")
    why_recommended: str = Field(default="", description="Reason this hotel fits the user")
    rating: float = Field(default=0, description="Hotel rating (1-5)")
    amenities: List[str] = Field(default_factory=list, description="List of amenities")


class Stop(BaseModel):
    """A single stop / activity within a day's itinerary.

    The LLM only outputs context-dependent fields (id, why_recommended, duration,
    time-of-day).  All other fields (name, category, sub_category, cuisine_type,
    lat, lon) are reattached deterministically from the candidate
    place pool during the hydration step in planning_agent.py.
    """

    id: str = Field(description="Unique place identifier (matches a candidate place)")
    why_recommended: str = Field(default="", description="Why this stop fits the user (personalized)")
    estimated_duration_minutes: int = Field(default=60, description="Suggested visit duration")
    suggested_time_of_day: Literal["morning", "afternoon", "evening"] = Field(
        default="morning",
        description="Best time of day for this stop",
    )


class Day(BaseModel):
    """A single day in the itinerary."""

    day_number: int = Field(description="Day number (1-based)")
    theme: str = Field(default="", description="Theme or title for the day")
    stops: List[Stop] = Field(default_factory=list, description="Stops/activities for this day")


class ItineraryPlan(BaseModel):
    """
    Complete structured itinerary plan (stops only).

    Hotels are handled by the dedicated Hotel Agent (``hotel_agent.py``)
    after route optimization, so ``accommodation_suggestions`` has been
    removed from this schema.

    This is the top-level schema that the Planning Agent LLM fills via
    ``.with_structured_output()``, guaranteeing the ``days`` key is always
    present and valid.
    """

    destination: str = Field(description="Destination city name")
    duration_days: int = Field(default=3, description="Number of trip days")
    days: List[Day] = Field(
        default_factory=list,
        description="Day-by-day itinerary with stops",
    )
