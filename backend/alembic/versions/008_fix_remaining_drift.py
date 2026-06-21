"""Fix remaining schema drift detected by autogenerate.

Revision ID: 008_fix_remaining_drift
Revises: 007_fix_critical_schema_drift
Create Date: 2026-06-20

Changes:
- bookings: rename start_date_time -> start_datetime, end_date_time -> end_datetime
- days: change day_id from INTEGER to VARCHAR (UUID)
- itinerary_stops: change stop_id and day_id from INTEGER to VARCHAR (UUID)
- users: change traveler_persona from TEXT to VARCHAR
- trips: add index on conversation_id
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "008_fix_remaining_drift"
down_revision: Union[str, None] = "007_fix_critical_schema_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    # ── Bookings: rename columns (only if old names exist) ──────────────────
    if _column_exists("bookings", "start_date_time"):
        op.execute("ALTER TABLE bookings RENAME COLUMN start_date_time TO start_datetime")
    if _column_exists("bookings", "end_date_time"):
        op.execute("ALTER TABLE bookings RENAME COLUMN end_date_time TO end_datetime")

    # ── Days: change day_id from INTEGER to VARCHAR ──────────────────────────
    # First drop any dependent FKs, then alter type
    op.execute("""
        DO $$
        BEGIN
            -- Drop FK from itinerary_stops.day_id if it exists
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'itinerary_stops_day_id_fkey'
            ) THEN
                ALTER TABLE itinerary_stops DROP CONSTRAINT itinerary_stops_day_id_fkey;
            END IF;
        END$$
    """)
    # Cast day_id to VARCHAR, handling existing data
    op.execute("ALTER TABLE days ALTER COLUMN day_id DROP IDENTITY IF EXISTS")
    op.execute("ALTER TABLE days ALTER COLUMN day_id TYPE VARCHAR USING day_id::VARCHAR")

    # ── Itinerary stops: change stop_id and day_id to VARCHAR ────────────────
    op.execute("ALTER TABLE itinerary_stops ALTER COLUMN stop_id DROP IDENTITY IF EXISTS")
    op.execute("ALTER TABLE itinerary_stops ALTER COLUMN stop_id TYPE VARCHAR USING stop_id::VARCHAR")
    op.execute("ALTER TABLE itinerary_stops ALTER COLUMN day_id TYPE VARCHAR USING day_id::VARCHAR")
    # Re-create FK for day_id
    op.execute("""
        ALTER TABLE itinerary_stops
        ADD CONSTRAINT itinerary_stops_day_id_fkey
        FOREIGN KEY (day_id) REFERENCES days(day_id) ON DELETE CASCADE
    """)

    # ── Users: change traveler_persona from TEXT to VARCHAR ──────────────────
    if _column_exists("users", "traveler_persona"):
        op.execute("ALTER TABLE users ALTER COLUMN traveler_persona TYPE VARCHAR")

    # ── Trips: add index on conversation_id ──────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS ix_trips_conversation_id ON trips (conversation_id)")


def downgrade() -> None:
    # ── Trips: drop index ────────────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_trips_conversation_id")

    # ── Users: revert traveler_persona to TEXT ───────────────────────────────
    op.execute("ALTER TABLE users ALTER COLUMN traveler_persona TYPE TEXT")

    # ── Itinerary stops: revert stop_id and day_id to INTEGER ────────────────
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'itinerary_stops_day_id_fkey'
            ) THEN
                ALTER TABLE itinerary_stops DROP CONSTRAINT itinerary_stops_day_id_fkey;
            END IF;
        END$$
    """)
    op.execute("ALTER TABLE itinerary_stops ALTER COLUMN day_id TYPE INTEGER USING day_id::INTEGER")
    op.execute("ALTER TABLE itinerary_stops ALTER COLUMN stop_id TYPE INTEGER USING stop_id::INTEGER")
    op.execute("ALTER TABLE itinerary_stops ALTER COLUMN stop_id ADD GENERATED ALWAYS AS IDENTITY")
    op.execute("""
        ALTER TABLE itinerary_stops
        ADD CONSTRAINT itinerary_stops_day_id_fkey
        FOREIGN KEY (day_id) REFERENCES days(day_id) ON DELETE CASCADE
    """)

    # ── Days: revert day_id to INTEGER ───────────────────────────────────────
    op.execute("ALTER TABLE days ALTER COLUMN day_id TYPE INTEGER USING day_id::INTEGER")
    op.execute("ALTER TABLE days ALTER COLUMN day_id ADD GENERATED ALWAYS AS IDENTITY")

    # ── Bookings: rename columns back ────────────────────────────────────────
    op.execute("ALTER TABLE bookings RENAME COLUMN start_datetime TO start_date_time")
    op.execute("ALTER TABLE bookings RENAME COLUMN end_datetime TO end_date_time")
