"""Initial schema — aligned with updated class diagram.

Revision ID: 001_initial
Revises: None
Create Date: 2026-06-18

Changes from previous schema:
- Removed: password_hash (users), Location, OpeningHours, Reservation tables
- Removed: Hotel/Restaurant/Attraction (replaced by composition *Details tables)
- Renamed: UploadedImage -> Image, TravelerProfile -> BehavioralProfile
- Added: Quiz, BehavioralProfile, HotelDetails, RestaurantDetails, AttractionDetails
- Added enums: PlaceCategory, RecommendationType/Status, PaceStyle, SpendingStyle,
  ExperienceLean, DayRhythm, AttractionPreference, SocialStyle
- Removed enums: TravelDimension, ReviewSource, ReservationStatus
- Restructured: Booking (trip_id FK, start/end datetime), Recommendation (trip_id FK),
  Feedback (trip_id FK), Review (simplified), Place (inlined location fields)
- Renamed columns: last_modified -> updated_at, helpful_count -> likes_count, etc.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    trip_status = sa.Enum("planning", "active", "completed", name="trip_status")
    trip_status.create(op.get_bind(), checkfirst=True)

    itinerary_status = sa.Enum("draft", "active", "archived", name="itinerary_status")
    itinerary_status.create(op.get_bind(), checkfirst=True)

    stop_status = sa.Enum("planned", "visited", "skipped", "cancelled", name="stop_status")
    stop_status.create(op.get_bind(), checkfirst=True)

    travel_mode = sa.Enum("walking", "driving", "transit", "cycling", name="travel_mode")
    travel_mode.create(op.get_bind(), checkfirst=True)

    booking_type = sa.Enum("hotel", "restaurant", "activity", "transport", name="booking_type")
    booking_type.create(op.get_bind(), checkfirst=True)

    booking_status = sa.Enum("pending", "confirmed", "cancelled", "completed", name="booking_status")
    booking_status.create(op.get_bind(), checkfirst=True)

    payment_method = sa.Enum("credit_card", "debit_card", "paypal", "cash", name="payment_method")
    payment_method.create(op.get_bind(), checkfirst=True)

    payment_status = sa.Enum("pending", "completed", "failed", "refunded", name="payment_status")
    payment_status.create(op.get_bind(), checkfirst=True)

    recommendation_type = sa.Enum("place", "activity", "restaurant", "hotel", name="recommendation_type")
    recommendation_type.create(op.get_bind(), checkfirst=True)

    recommendation_status = sa.Enum("pending", "accepted", "rejected", "expired", name="recommendation_status")
    recommendation_status.create(op.get_bind(), checkfirst=True)

    feedback_type = sa.Enum("thumbs_up", "thumbs_down", "rating", "comment", name="feedback_type")
    feedback_type.create(op.get_bind(), checkfirst=True)

    conversation_status = sa.Enum("active", "archived", "closed", name="conversation_status")
    conversation_status.create(op.get_bind(), checkfirst=True)

    processing_status = sa.Enum("pending", "processing", "completed", "failed", name="processing_status")
    processing_status.create(op.get_bind(), checkfirst=True)

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", sa.String, primary_key=True),
        sa.Column("email", sa.String, unique=True, nullable=False),
        sa.Column("full_name", sa.String, nullable=True),
        sa.Column("phone_number", sa.String, nullable=True),
        sa.Column("registration_date", sa.DateTime, server_default=sa.func.now()),
        sa.Column("home_city", sa.String, nullable=True),
        sa.Column("quiz_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("profile_id", sa.String, nullable=True),
    )

    # ── behavioral_profiles ──────────────────────────────────────────────────
    op.create_table(
        "behavioral_profiles",
        sa.Column("profile_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False, unique=True),
        sa.Column("pace_style", sa.String, nullable=True),
        sa.Column("spending_style", sa.String, nullable=True),
        sa.Column("experience_lean", sa.String, nullable=True),
        sa.Column("day_rhythm", sa.String, nullable=True),
        sa.Column("attraction_preference", sa.String, nullable=True),
        sa.Column("social_style", sa.String, nullable=True),
        sa.Column("interests", JSON, nullable=True),
        sa.Column("dining_preferences", JSON, nullable=True),
        sa.Column("accommodation_preferences", JSON, nullable=True),
        sa.Column("custom_interests", JSON, nullable=True),
        sa.Column("persona_title", sa.String, nullable=True),
        sa.Column("persona_summary", sa.Text, nullable=True),
        sa.Column("quiz_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_behavioral_profiles_user_id", "behavioral_profiles", ["user_id"], unique=True)

    # ── quizzes ──────────────────────────────────────────────────────────────
    op.create_table(
        "quizzes",
        sa.Column("quiz_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("answers", JSON, nullable=True),
        sa.Column("is_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])

    # ── places ───────────────────────────────────────────────────────────────
    op.create_table(
        "places",
        sa.Column("place_id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("rating", sa.Float, nullable=True),
        sa.Column("review_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("popularity_score", sa.Float, nullable=True),
        sa.Column("phone", sa.String, nullable=True),
        sa.Column("website", sa.String, nullable=True),
        sa.Column("maps_link", sa.String, nullable=True),
        sa.Column("address", sa.String, nullable=True),
        sa.Column("city", sa.String, nullable=True),
        sa.Column("country", sa.String, nullable=True),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lng", sa.Float, nullable=True),
        sa.Column("timezone", sa.String, nullable=True),
        sa.Column("photo_urls", JSON, nullable=True),
        sa.Column("embedding", JSON, nullable=True),
    )

    # ── hotel_details ────────────────────────────────────────────────────────
    op.create_table(
        "hotel_details",
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("star_class", sa.Integer, nullable=True),
        sa.Column("nightly_rate", sa.Float, nullable=True),
        sa.Column("amenities", JSON, nullable=True),
        sa.Column("booking_platforms", JSON, nullable=True),
    )

    # ── restaurant_details ───────────────────────────────────────────────────
    op.create_table(
        "restaurant_details",
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cuisine_type", sa.String, nullable=True),
        sa.Column("avg_cost_per_person", sa.Float, nullable=True),
        sa.Column("opening_hours", JSON, nullable=True),
    )

    # ── attraction_details ───────────────────────────────────────────────────
    op.create_table(
        "attraction_details",
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("subcategory", sa.String, nullable=True),
        sa.Column("tags", JSON, nullable=True),
        sa.Column("entry_fee", sa.Float, nullable=True),
        sa.Column("opening_hours", JSON, nullable=True),
    )

    # ── trips ────────────────────────────────────────────────────────────────
    op.create_table(
        "trips",
        sa.Column("trip_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("trip_name", sa.String, nullable=True),
        sa.Column("destination", sa.String, nullable=False),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("number_of_travelers", sa.Integer, server_default=sa.text("1")),
        sa.Column("budget", sa.Float, nullable=True),
        sa.Column("preferences", JSON, nullable=True),
        sa.Column("status", sa.Enum(name="trip_status"), nullable=False, server_default="planning"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])

    # ── itineraries ──────────────────────────────────────────────────────────
    op.create_table(
        "itineraries",
        sa.Column("itinerary_id", sa.String, primary_key=True),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, server_default=sa.text("1")),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("total_estimated_cost", sa.Float, nullable=True),
        sa.Column("status", sa.Enum(name="itinerary_status"), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_itineraries_trip_id", "itineraries", ["trip_id"])

    # ── days ─────────────────────────────────────────────────────────────────
    op.create_table(
        "days",
        sa.Column("day_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("itinerary_id", sa.String, sa.ForeignKey("itineraries.itinerary_id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_number", sa.Integer, nullable=False),
        sa.Column("date", sa.Date, nullable=True),
        sa.Column("theme", sa.String, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
    )
    op.create_index("ix_days_itinerary_id", "days", ["itinerary_id"])

    # ── itinerary_stops ──────────────────────────────────────────────────────
    op.create_table(
        "itinerary_stops",
        sa.Column("stop_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day_id", sa.Integer, sa.ForeignKey("days.day_id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id"), nullable=True),
        sa.Column("place_snapshot", JSON, nullable=True),
        sa.Column("scheduled_time", sa.Time, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("order_in_day", sa.Integer, server_default=sa.text("0")),
        sa.Column("minutes_from_prev_stop", sa.Integer, nullable=True),
        sa.Column("travel_mode", sa.Enum(name="travel_mode"), nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("ai_notes", sa.Text, nullable=True),
        sa.Column("user_notes", sa.Text, nullable=True),
        sa.Column("status", sa.Enum(name="stop_status"), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_itinerary_stops_day_id", "itinerary_stops", ["day_id"])

    # ── bookings ─────────────────────────────────────────────────────────────
    op.create_table(
        "bookings",
        sa.Column("booking_id", sa.String, primary_key=True),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id"), nullable=True),
        sa.Column("booking_type", sa.Enum(name="booking_type"), nullable=False),
        sa.Column("confirmation_number", sa.String, nullable=True),
        sa.Column("booking_date", sa.DateTime, server_default=sa.func.now()),
        sa.Column("start_datetime", sa.DateTime, nullable=True),
        sa.Column("end_datetime", sa.DateTime, nullable=True),
        sa.Column("total_cost", sa.Float, nullable=True),
        sa.Column("status", sa.Enum(name="booking_status"), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_bookings_trip_id", "bookings", ["trip_id"])

    # ── payments ─────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("payment_id", sa.String, primary_key=True),
        sa.Column("booking_id", sa.String, sa.ForeignKey("bookings.booking_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("payment_method", sa.Enum(name="payment_method"), nullable=False),
        sa.Column("status", sa.Enum(name="payment_status"), nullable=False, server_default="pending"),
        sa.Column("transaction_reference", sa.String, nullable=True),
        sa.Column("paid_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])

    # ── receipts ─────────────────────────────────────────────────────────────
    op.create_table(
        "receipts",
        sa.Column("receipt_id", sa.String, primary_key=True),
        sa.Column("payment_id", sa.String, sa.ForeignKey("payments.payment_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("receipt_number", sa.String, nullable=False),
        sa.Column("issue_date", sa.DateTime, server_default=sa.func.now()),
        sa.Column("subtotal", sa.Float, nullable=False),
        sa.Column("tax", sa.Float, nullable=True),
        sa.Column("total", sa.Float, nullable=False),
    )
    op.create_index("ix_receipts_payment_id", "receipts", ["payment_id"])

    # ── recommendations ──────────────────────────────────────────────────────
    op.create_table(
        "recommendations",
        sa.Column("recommendation_id", sa.String, primary_key=True),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("recommendation_type", sa.Enum(name="recommendation_type"), nullable=True),
        sa.Column("status", sa.Enum(name="recommendation_status"), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_recommendations_trip_id", "recommendations", ["trip_id"])
    op.create_index("ix_recommendations_place_id", "recommendations", ["place_id"])

    # ── reviews ──────────────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("review_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("review_date", sa.DateTime, server_default=sa.func.now()),
        sa.Column("likes_count", sa.Integer, server_default=sa.text("0")),
    )
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_place_id", "reviews", ["place_id"])

    # ── feedbacks ────────────────────────────────────────────────────────────
    op.create_table(
        "feedbacks",
        sa.Column("feedback_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=True),
        sa.Column("feedback_type", sa.Enum(name="feedback_type"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"])
    op.create_index("ix_feedbacks_trip_id", "feedbacks", ["trip_id"])

    # ── saved_places ─────────────────────────────────────────────────────────
    op.create_table(
        "saved_places",
        sa.Column("saved_place_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id"), nullable=False),
        sa.Column("saved_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("note", sa.Text, nullable=True),
    )
    op.create_index("ix_saved_places_user_id", "saved_places", ["user_id"])
    op.create_index("ix_saved_places_place_id", "saved_places", ["place_id"])

    # ── images ───────────────────────────────────────────────────────────────
    op.create_table(
        "images",
        sa.Column("image_id", sa.String, primary_key=True),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("file_name", sa.String, nullable=False),
        sa.Column("file_url", sa.String, nullable=True),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("analysis_status", sa.Enum(name="processing_status"), nullable=False, server_default="pending"),
    )
    op.create_index("ix_images_trip_id", "images", ["trip_id"])
    op.create_index("ix_images_user_id", "images", ["user_id"])

    # ── image_features ───────────────────────────────────────────────────────
    op.create_table(
        "image_features",
        sa.Column("feature_id", sa.String, primary_key=True),
        sa.Column("image_id", sa.String, sa.ForeignKey("images.image_id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_type", sa.String, nullable=False),
        sa.Column("feature_name", sa.String, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("value", sa.String, nullable=True),
        sa.Column("metadata", JSON, nullable=True),
    )
    op.create_index("ix_image_features_image_id", "image_features", ["image_id"])

    # ── conversations ────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("status", sa.Enum(name="conversation_status"), nullable=False, server_default="active"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_trip_id", "conversations", ["trip_id"])

    # ── messages ─────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String, primary_key=True),
        sa.Column("conversation_id", sa.String, sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("image_features")
    op.drop_table("images")
    op.drop_table("saved_places")
    op.drop_table("feedbacks")
    op.drop_table("reviews")
    op.drop_table("recommendations")
    op.drop_table("receipts")
    op.drop_table("payments")
    op.drop_table("bookings")
    op.drop_table("itinerary_stops")
    op.drop_table("days")
    op.drop_table("itineraries")
    op.drop_table("trips")
    op.drop_table("attraction_details")
    op.drop_table("restaurant_details")
    op.drop_table("hotel_details")
    op.drop_table("places")
    op.drop_table("quizzes")
    op.drop_table("behavioral_profiles")
    op.drop_table("users")

    # Drop enums
    sa.Enum(name="processing_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="conversation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="feedback_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recommendation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="recommendation_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payment_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payment_method").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="booking_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="booking_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="travel_mode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stop_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="itinerary_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="trip_status").drop(op.get_bind(), checkfirst=True)
