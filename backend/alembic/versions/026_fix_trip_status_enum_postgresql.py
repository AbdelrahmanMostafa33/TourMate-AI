"""Fix TripStatus enum for PostgreSQL — add missing booking/payment values.

Revision ID: 026_fix_trip_status_pg
Revises: 025_update_trip_status_enum
Create Date: 2026-07-01

Background:
  Migration 025_update_trip_status_enum was a NO-OP (assumed SQLite, but
  the actual database is PostgreSQL). The `trip_status` ENUM type in
  PostgreSQL still has only the original 3 values (planning, active,
  completed) from the initial migration.

  This migration adds the missing values so that the PATCH /trips/{id}/status
  endpoint can set statuses like 'awaiting_booking' without getting a
  PostgreSQL ENUM violation error.

Values to add:
  - itinerary_draft
  - awaiting_booking
  - booking_pending
  - payment_processing
  - payment_failed
  - booking_confirmed
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "026_fix_trip_status_pg"
down_revision: Union[str, None] = "025_update_trip_status_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_STATUSES = [
    "itinerary_draft",
    "awaiting_booking",
    "booking_pending",
    "payment_processing",
    "payment_failed",
    "booking_confirmed",
]


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # PostgreSQL has a strict ENUM. Add the new values one at a time.
        # IF NOT EXISTS makes this idempotent (safe to re-run).
        # String interpolation is safe here because values are hardcoded.
        for new_status in NEW_STATUSES:
            op.execute(
                f"ALTER TYPE trip_status ADD VALUE IF NOT EXISTS '{new_status}'"
            )
    else:
        # SQLite stores enums as TEXT — no schema change needed.
        pass


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # PostgreSQL cannot remove a value from an enum without recreating
        # the type.  For dev/local environments, the simplest approach is
        # to skip downgrade (rarely needed for enum additions).
        pass
    else:
        pass
