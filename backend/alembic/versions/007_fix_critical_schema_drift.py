"""Fix critical schema drift across 8 tables.

Revision ID: 007_fix_critical_schema_drift
Revises: 006_fix_schema_drift
Create Date: 2026-06-20

Changes:
- users: add traveler_persona, updated_at; drop quiz_completed, profile_id
- trips: add traveler_group_type, conversation_id, updated_at, approved_at
- bookings: add provider, provider_reference, currency, raw_response, updated_at
- payments: add currency, provider, stripe_payment_intent_id, raw_response, updated_at
- receipts: add currency
- conversations: drop trip_id (FK moved to trips.conversation_id)
- saved_places: add updated_at
- itinerary_stops: add classification, importance_score, time_of_day
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "007_fix_critical_schema_drift"
down_revision: Union[str, None] = "006_fix_schema_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Ensure enum types exist (created in migration 002, may need re-creation) ──
    sa.Enum("solo", "couple", "family", "friends", "business", name="traveler_group_type").create(op.get_bind(), checkfirst=True)
    sa.Enum("must_see", "nice_to_have", "optional", name="stop_classification").create(op.get_bind(), checkfirst=True)
    sa.Enum("morning", "afternoon", "evening", "night", name="time_of_day").create(op.get_bind(), checkfirst=True)
    sa.Enum("direct", "booking_com", "expedia", "airbnb", "other", name="booking_provider").create(op.get_bind(), checkfirst=True)
    sa.Enum("stripe", "paypal", "apple_pay", "google_pay", "other", name="payment_provider").create(op.get_bind(), checkfirst=True)

    # ── Users: add columns, drop old ────────────────────────────────────────
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS traveler_persona TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS quiz_completed")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_id")

    # ── Trips: add missing columns ──────────────────────────────────────────
    op.execute("ALTER TABLE trips ADD COLUMN IF NOT EXISTS traveler_group_type traveler_group_type")
    op.execute("ALTER TABLE trips ADD COLUMN IF NOT EXISTS conversation_id VARCHAR")
    op.execute("ALTER TABLE trips ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE trips ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP")
    # Add FK for conversation_id if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'trips_conversation_id_fkey'
            ) THEN
                ALTER TABLE trips ADD CONSTRAINT trips_conversation_id_fkey
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id);
            END IF;
        END$$
    """)

    # ── Bookings: add missing columns ───────────────────────────────────────
    op.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS provider booking_provider")
    op.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS provider_reference VARCHAR")
    op.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS currency VARCHAR(3)")
    op.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS raw_response JSON")
    op.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
    # Add index for user_id if not exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_user_id ON bookings (user_id)")

    # ── Payments: add missing columns ───────────────────────────────────────
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency VARCHAR(3)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS provider payment_provider")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS stripe_payment_intent_id VARCHAR")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS raw_response JSON")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")

    # ── Receipts: add currency ──────────────────────────────────────────────
    op.execute("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS currency VARCHAR(3)")

    # ── Conversations: drop old trip_id FK ──────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'conversations_trip_id_fkey'
            ) THEN
                ALTER TABLE conversations DROP CONSTRAINT conversations_trip_id_fkey;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'conversations' AND column_name = 'trip_id'
            ) THEN
                ALTER TABLE conversations DROP COLUMN trip_id;
            END IF;
        END$$
    """)

    # ── Saved places: add updated_at ────────────────────────────────────────
    op.execute("ALTER TABLE saved_places ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")

    # ── Itinerary stops: add missing columns ────────────────────────────────
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS classification stop_classification")
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS importance_score INTEGER")
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS time_of_day time_of_day")


def downgrade() -> None:
    # ── Itinerary stops: drop added columns ─────────────────────────────────
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS time_of_day")
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS importance_score")
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS classification")

    # ── Saved places: drop updated_at ───────────────────────────────────────
    op.execute("ALTER TABLE saved_places DROP COLUMN IF EXISTS updated_at")

    # ── Conversations: restore trip_id ──────────────────────────────────────
    op.execute("ALTER TABLE conversations ADD COLUMN trip_id VARCHAR")
    op.execute("""
        ALTER TABLE conversations ADD CONSTRAINT conversations_trip_id_fkey
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE
    """)

    # ── Receipts: drop currency ─────────────────────────────────────────────
    op.execute("ALTER TABLE receipts DROP COLUMN IF EXISTS currency")

    # ── Payments: drop added columns ────────────────────────────────────────
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS raw_response")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS stripe_payment_intent_id")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS provider")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS currency")

    # ── Bookings: drop added columns ────────────────────────────────────────
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS raw_response")
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS provider_reference")
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS provider")

    # ── Trips: drop added columns ───────────────────────────────────────────
    op.execute("ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_conversation_id_fkey")
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS approved_at")
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS conversation_id")
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS traveler_group_type")

    # ── Users: restore old columns, drop new ────────────────────────────────
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS traveler_persona")
    op.execute("ALTER TABLE users ADD COLUMN profile_id VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN quiz_completed BOOLEAN DEFAULT FALSE")
