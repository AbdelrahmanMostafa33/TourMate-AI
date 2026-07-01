"""All enums referenced in the TourMate AI class diagram."""

from enum import Enum as PyEnum


# ─── Trip ──────────────────────────────────────────────────────────────────

class TripStatus(str, PyEnum):
    # Planning Phase
    planning              = "planning"           # Initial state, AI conversation active
    itinerary_draft       = "itinerary_draft"    # Itinerary created but not finalized

    # Booking & Payment Phase
    awaiting_booking      = "awaiting_booking"   # Itinerary approved, ready for bookings
    booking_pending       = "booking_pending"    # Bookings created, awaiting payment
    payment_processing    = "payment_processing" # Payments being processed
    payment_failed        = "payment_failed"     # Payment failed, retry needed

    # Confirmation Phase
    booking_confirmed     = "booking_confirmed"  # All bookings paid and confirmed

    # Active Phase
    active                = "active"              # Trip is ongoing

    # Completion Phase
    completed             = "completed"           # Trip finished


class ItineraryStatus(str, PyEnum):
    draft    = "draft"
    active   = "active"
    archived = "archived"


class StopStatus(str, PyEnum):
    planned   = "planned"
    visited   = "visited"
    skipped   = "skipped"
    cancelled = "cancelled"


class TravelMode(str, PyEnum):
    walking = "walking"
    driving = "driving"
    transit = "transit"
    cycling = "cycling"


class TimeOfDay(str, PyEnum):
    MORNING    = "morning"
    AFTERNOON  = "afternoon"
    EVENING    = "evening"
    NIGHT      = "night"


# ─── Place ───────────────────────────────────────────────────────────────────

class PlaceCategory(str, PyEnum):
    hotel      = "hotel"
    restaurant = "restaurant"
    attraction = "attraction"


class AccommodationType(str, PyEnum):
    hotel    = "hotel"
    hostel   = "hostel"
    resort   = "resort"
    luxury   = "luxury"


# ─── Booking & Payment ───────────────────────────────────────────────────────

class BookingType(str, PyEnum):
    hotel      = "hotel"
    transport  = "transport"
    flight     = "flight"


class BookingProvider(str, PyEnum):
    direct     = "direct"
    booking_com = "booking_com"
    airbnb     = "airbnb"
    amadeus    = "amadeus"
    other      = "other"


class BookingStatus(str, PyEnum):
    pending   = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class PaymentMethod(str, PyEnum):
    credit_card = "credit_card"
    debit_card  = "debit_card"
    paypal      = "paypal"
    cash        = "cash"


class PaymentStatus(str, PyEnum):
    pending   = "pending"
    completed = "completed"
    failed    = "failed"
    refunded  = "refunded"


class PaymentProvider(str, PyEnum):
    stripe     = "stripe"
    paypal     = "paypal"
    apple_pay  = "apple_pay"
    google_pay = "google_pay"
    other      = "other"


# ─── Trip Profiles (per-trip AI-generated profiles) ─────────────────────────

class BudgetLevel(str, PyEnum):
    BUDGET = "budget"
    MODERATE = "moderate"
    LUXURY = "luxury"


class TravelStyle(str, PyEnum):
    ROMANTIC = "romantic"
    ADVENTURE = "adventure"
    FAMILY = "family"
    BUSINESS = "business"
    SOLO = "solo"
    CULTURAL = "cultural"
    RELAXATION = "relaxation"


class TripPace(str, PyEnum):
    PACKED = "packed"
    MODERATE = "moderate"
    RELAXED = "relaxed"


# ─── Profile & Feedback ──────────────────────────────────────────────────────

class FeedbackType(str, PyEnum):
    thumbs_up   = "thumbs_up"
    thumbs_down = "thumbs_down"
    rating      = "rating"
    comment     = "comment"


# ─── Chat ────────────────────────────────────────────────────────────────────

class ConversationStatus(str, PyEnum):
    active   = "active"
    archived = "archived"
    closed   = "closed"


# ─── Image ───────────────────────────────────────────────────────────────────

class ProcessingStatus(str, PyEnum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"
