"""All enums referenced in the TourMate AI class diagram."""

from enum import Enum as PyEnum


# ─── Trip & Itinerary ────────────────────────────────────────────────────────

class TripStatus(str, PyEnum):
    planning  = "planning"
    active    = "active"
    completed = "completed"


class ItineraryStatus(str, PyEnum):
    draft    = "draft"
    approved = "approved"
    rejected = "rejected"
    active   = "active"


class StopStatus(str, PyEnum):
    planned  = "planned"
    visited  = "visited"
    skipped  = "skipped"
    cancelled = "cancelled"


class TravelMode(str, PyEnum):
    walking  = "walking"
    driving  = "driving"
    transit  = "transit"
    cycling  = "cycling"


# ─── Place ───────────────────────────────────────────────────────────────────

class ReviewSource(str, PyEnum):
    google     = "google"
    tripadvisor = "tripadvisor"
    yelp       = "yelp"
    user       = "user"


# ─── Booking & Payment ───────────────────────────────────────────────────────

class BookingType(str, PyEnum):
    hotel      = "hotel"
    restaurant = "restaurant"
    activity   = "activity"
    transport  = "transport"


class BookingStatus(str, PyEnum):
    pending   = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class ReservationStatus(str, PyEnum):
    pending   = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    no_show   = "no_show"


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


# ─── Profile & Feedback ──────────────────────────────────────────────────────

class TravelDimension(str, PyEnum):
    ADVENTURE = "ADVENTURE"
    CULTURE   = "CULTURE"
    LOCAL     = "LOCAL"
    LUXURY    = "LUXURY"
    NIGHTLIFE = "NIGHTLIFE"
    SOCIAL    = "SOCIAL"


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
