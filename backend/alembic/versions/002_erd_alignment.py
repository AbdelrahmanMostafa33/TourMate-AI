"""Align models with ERD — trip_profiles, missing columns, FK fixes.

Revision ID: 002_erd_alignment
Revises: 001_initial
Create Date: 2026-06-19

Changes:
- Drop behavioral_profiles, quizzes tables (replaced by trip_profiles)
- Create trip_profiles table per ERD
- Add missing columns: trips.traveler_group_type, trips.conversation_id,
  trips.updated_at, trips.approved_at
- Add missing columns: bookings.user_id, bookings.provider, bookings.provider_reference,
  bookings.currency, bookings.raw_response, bookings.updated_at
- Add missing columns: payments.currency, payments.provider,
  payments.stripe_payment_intent_id, payments.raw_response, payments.updated_at
- Add missing columns: receipts.currency
- Add missing columns: places.price_level, places.opening_hours
- Add missing columns: itinerary_stops.classification, itinerary_stops.importance_score,
  itinerary_stops.time_of_day
- Add missing columns: saved_places.updated_at
- Add missing columns: users.traveler_persona, users.updated_at
- Remove users.quiz_completed, users.profile_id
- Fix conversations FK: remove trip_id from conversations, add conversation_id to trips
- Create event_log table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "002_erd_alignment"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New Enums ─────────────────────────────────────────────────────────────
    traveler_group_type = sa.Enum("solo", "couple", "family", "friends", "business", name="traveler_group_type")
    traveler_group_type.create(op.get_bind(), checkfirst=True)

    stop_classification = sa.Enum("must_see", "nice_to_have", "optional", name="stop_classification")
    stop_classification.create(op.get_bind(), checkfirst=True)

    time_of_day = sa.Enum("morning", "afternoon", "evening", "night", name="time_of_day")
    time_of_day.create(op.get_bind(), checkfirst=True)

    booking_provider = sa.Enum("direct", "booking_com", "expedia", "airbnb", "other", name="booking_provider")
    booking_provider.create(op.get_bind(), checkfirst=True)

    payment_provider = sa.Enum("stripe", "paypal", "apple_pay", "google_pay", "other", name="payment_provider")
    payment_provider.create(op.get_bind(), checkfirst=True)

    # ── Drop old tables ───────────────────────────────────────────────────────
    op.drop_table("quizzes")
    op.drop_table("behavioral_profiles")

    # ── Create trip_profiles ───────────────────────────────────────────────────
    op.create_table(
        "trip_profiles",
        sa.Column("profile_id", sa.String, primary_key=True),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_level", sa.String, nullable=True),
        sa.Column("travel_style", sa.String, nullable=True),
        sa.Column("pace", sa.String, nullable=True),
        sa.Column("interests", JSON, nullable=True),
        sa.Column("food_preferences", JSON, nullable=True),
        sa.Column("accommodation_preferences", JSON, nullable=True),
        sa.Column("luxury_score", sa.Float, nullable=True),
        sa.Column("culture_score", sa.Float, nullable=True),
        sa.Column("adventure_score", sa.Float, nullable=True),
        sa.Column("shopping_score", sa.Float, nullable=True),
        sa.Column("family_score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_trip_profiles_trip_id", "trip_profiles", ["trip_id"])

    # ── Users: add columns, remove old ────────────────────────────────────────
    op.add_column("users", sa.Column("traveler_persona", sa.Text, nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))
    op.drop_column("users", "quiz_completed")
    op.drop_column("users", "profile_id")

    # ── Trips: add missing columns ────────────────────────────────────────────
    op.add_column("trips", sa.Column("traveler_group_type", sa.Enum(name="traveler_group_type"), nullable=True))
    op.add_column("trips", sa.Column("conversation_id", sa.String, sa.ForeignKey("conversations.conversation_id"), nullable=True))
    op.add_column("trips", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))
    op.add_column("trips", sa.Column("approved_at", sa.DateTime, nullable=True))

    # ── Conversations: remove trip_id FK (now on trips) ───────────────────────
    op.drop_constraint("conversations_trip_id_fkey", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_trip_id", table_name="conversations")
    op.drop_column("conversations", "trip_id")

    # ── Bookings: add missing columns ─────────────────────────────────────────
    op.add_column("bookings", sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False))
    op.add_column("bookings", sa.Column("provider", sa.Enum(name="booking_provider"), nullable=True))
    op.add_column("bookings", sa.Column("provider_reference", sa.String, nullable=True))
    op.add_column("bookings", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("bookings", sa.Column("raw_response", JSON, nullable=True))
    op.add_column("bookings", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])

    # ── Payments: add missing columns ─────────────────────────────────────────
    op.add_column("payments", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("payments", sa.Column("provider", sa.Enum(name="payment_provider"), nullable=True))
    op.add_column("payments", sa.Column("stripe_payment_intent_id", sa.String, nullable=True))
    op.add_column("payments", sa.Column("raw_response", JSON, nullable=True))
    op.add_column("payments", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))

    # ── Receipts: add currency ────────────────────────────────────────────────
    op.add_column("receipts", sa.Column("currency", sa.String(3), nullable=True))

    # ── Places: add missing columns ───────────────────────────────────────────
    op.add_column("places", sa.Column("price_level", sa.Integer, nullable=True))
    op.add_column("places", sa.Column("opening_hours", JSON, nullable=True))

    # ── Itinerary Stops: add missing columns ──────────────────────────────────
    op.add_column("itinerary_stops", sa.Column("classification", sa.Enum(name="stop_classification"), nullable=True))
    op.add_column("itinerary_stops", sa.Column("importance_score", sa.Integer, nullable=True))
    op.add_column("itinerary_stops", sa.Column("time_of_day", sa.Enum(name="time_of_day"), nullable=True))

    # ── Saved Places: add updated_at ──────────────────────────────────────────
    op.add_column("saved_places", sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()))

    # ── Event Log table ───────────────────────────────────────────────────────
    op.create_table(
        "event_log",
        sa.Column("log_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id"), nullable=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("event_data", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_event_log_user_id", "event_log", ["user_id"])
    op.create_index("ix_event_log_trip_id", "event_log", ["trip_id"])


def downgrade() -> None:
    # ── Drop event_log ────────────────────────────────────────────────────────
    op.drop_index("ix_event_log_trip_id", table_name="event_log")
    op.drop_index("ix_event_log_user_id", table_name="event_log")
    op.drop_table("event_log")

    # ── Saved Places: remove updated_at ───────────────────────────────────────
    op.drop_column("saved_places", "updated_at")

    # ── Itinerary Stops: remove columns ───────────────────────────────────────
    op.drop_column("itinerary_stops", "time_of_day")
    op.drop_column("itinerary_stops", "importance_score")
    op.drop_column("itinerary_stops", "classification")

    # ── Places: remove columns ────────────────────────────────────────────────
    op.drop_column("places", "opening_hours")
    op.drop_column("places", "price_level")

    # ── Receipts: remove currency ─────────────────────────────────────────────
    op.drop_column("receipts", "currency")

    # ── Payments: remove columns ──────────────────────────────────────────────
    op.drop_column("payments", "updated_at")
    op.drop_column("payments", "raw_response")
    op.drop_column("payments", "stripe_payment_intent_id")
    op.drop_column("payments", "provider")
    op.drop_column("payments", "currency")

    # ── Bookings: remove columns ──────────────────────────────────────────────
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_column("bookings", "updated_at")
    op.drop_column("bookings", "raw_response")
    op.drop_column("bookings", "currency")
    op.drop_column("bookings", "provider_reference")
    op.drop_column("bookings", "provider")
    op.drop_column("bookings", "user_id")

    # ── Conversations: restore trip_id FK ─────────────────────────────────────
    op.add_column("conversations", sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False))
    op.create_index("ix_conversations_trip_id", "conversations", ["trip_id"])

    # ── Trips: remove columns ─────────────────────────────────────────────────
    op.drop_column("trips", "approved_at")
    op.drop_column("trips", "updated_at")
    op.drop_column("trips", "conversation_id")
    op.drop_column("trips", "traveler_group_type")

    # ── Users: restore old columns ────────────────────────────────────────────
    op.add_column("users", sa.Column("profile_id", sa.String, nullable=True))
    op.add_column("users", sa.Column("quiz_completed", sa.Boolean, server_default=sa.text("false")))
    op.drop_column("users", "updated_at")
    op.drop_column("users", "traveler_persona")

    # ── Drop trip_profiles ────────────────────────────────────────────────────
    op.drop_index("ix_trip_profiles_trip_id", table_name="trip_profiles")
    op.drop_table("trip_profiles")

    # ── Restore old tables ────────────────────────────────────────────────────
    op.create_table(
        "quizzes",
        sa.Column("quiz_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("answers", JSON, nullable=True),
        sa.Column("is_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])

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

    # ── Drop enums ────────────────────────────────────────────────────────────
    sa.Enum(name="payment_provider").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="booking_provider").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="time_of_day").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stop_classification").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="traveler_group_type").drop(op.get_bind(), checkfirst=True)
