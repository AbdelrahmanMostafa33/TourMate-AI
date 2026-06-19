"""All enums referenced in the TourMate AI class diagram."""

from enum import Enum as PyEnum


# ─── Trip ──────────────────────────────────────────────────────────────────

class TripStatus(str, PyEnum):
    planning  = "planning"
    active    = "active"
    completed = "completed"


class TravelerGroupType(str, PyEnum):
    SOLO        = "solo"
    COUPLE      = "couple"
    FAMILY      = "family"
    FRIENDS     = "friends"
    BUSINESS    = "business"


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


class StopClassification(str, PyEnum):
    MUST_SEE   = "must_see"
    NICE_TO_HAVE = "nice_to_have"
    OPTIONAL   = "optional"


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


# ─── Booking & Payment ───────────────────────────────────────────────────────

class BookingType(str, PyEnum):
    hotel      = "hotel"
    restaurant = "restaurant"
    activity   = "activity"
    transport  = "transport"


class BookingProvider(str, PyEnum):
    direct     = "direct"
    booking_com = "booking_com"
    expedia    = "expedia"
    airbnb     = "airbnb"
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


# ─── Trip Profiles (per-trip AI-generated profiles) ─────────────────────────

class BudgetLevel(str, PyEnum):
    BUDGET = "BUDGET"
    MODERATE = "MODERATE"
    LUXURY = "LUXURY"


class TravelStyle(str, PyEnum):
    ROMANTIC = "ROMANTIC"
    ADVENTURE = "ADVENTURE"
    FAMILY = "FAMILY"
    BUSINESS = "BUSINESS"
    SOLO = "SOLO"
    CULTURAL = "CULTURAL"
    RELAXATION = "RELAXATION"


class TripPace(str, PyEnum):
    PACKED = "PACKED"
    BALANCED = "BALANCED"
    RELAXED = "RELAXED"


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
