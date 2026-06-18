"""All enums referenced in the TourMate AI class diagram."""

from enum import Enum as PyEnum


# ─── Trip & Itinerary ────────────────────────────────────────────────────────

class TripStatus(str, PyEnum):
    planning  = "planning"
    active    = "active"
    completed = "completed"


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


# ─── Place ───────────────────────────────────────────────────────────────────

class PlaceCategory(str, PyEnum):
    hotel      = "hotel"
    restaurant = "restaurant"
    attraction = "attraction"


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


# ─── Recommendation ─────────────────────────────────────────────────────────

class RecommendationType(str, PyEnum):
    place    = "place"
    activity = "activity"
    restaurant = "restaurant"
    hotel    = "hotel"


class RecommendationStatus(str, PyEnum):
    pending  = "pending"
    accepted = "accepted"
    rejected = "rejected"
    expired  = "expired"


# ─── Profile / Behavioral ───────────────────────────────────────────────────

class PaceStyle(str, PyEnum):
    ADVENTUROUS = "ADVENTUROUS"
    RELAXING    = "RELAXING"


class SpendingStyle(str, PyEnum):
    BUDGET_CONSCIOUS = "BUDGET_CONSCIOUS"
    LUXURIOUS       = "LUXURIOUS"


class ExperienceLean(str, PyEnum):
    NATURE_OUTDOORS = "NATURE_OUTDOORS"
    CULTURE         = "CULTURE"


class DayRhythm(str, PyEnum):
    EARLY_BIRD = "EARLY_BIRD"
    NIGHT_OWL  = "NIGHT_OWL"


class AttractionPreference(str, PyEnum):
    POPULAR = "POPULAR"
    LOCAL   = "LOCAL"


class SocialStyle(str, PyEnum):
    INDEPENDENT = "INDEPENDENT"
    SOCIAL      = "SOCIAL"


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
