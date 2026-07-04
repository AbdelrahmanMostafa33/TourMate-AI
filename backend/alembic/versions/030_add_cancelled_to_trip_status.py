"""Add 'cancelled' to TripStatus enum for PostgreSQL.

Revision ID: 030_add_cancelled_to_trip_status
Revises: e930583655d2
Create Date: 2026-07-04

Background:
  The Python-level ``TripStatus`` enum in ``models/enums.py`` was updated to
  include a ``cancelled`` value, but the PostgreSQL ``trip_status`` ENUM type
  still only has the values from the initial migration + 025/026 additions:

    (planning, active, completed, itinerary_draft, awaiting_booking,
     booking_pending, payment_processing, payment_failed, booking_confirmed)

  The new ``POST /trips/{trip_id}/cancel`` endpoint sets
  ``trip.status = TripStatus.cancelled`` and then calls ``db.commit()``,
  which fails with::

    InvalidTextRepresentationError: invalid input value for enum trip_status:
    "cancelled"

  This migration adds ``'cancelled'`` to the PostgreSQL enum so the cancel
  endpoint works at the database level.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "030_add_cancelled_to_trip_status"
down_revision: Union[str, None] = "e930583655d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # IF NOT EXISTS makes this idempotent (safe to re-run).
        op.execute(
            "ALTER TYPE trip_status ADD VALUE IF NOT EXISTS 'cancelled'"
        )
    else:
        # SQLite stores enums as TEXT — no schema change needed.
        pass


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # PostgreSQL cannot remove a value from an enum without recreating
        # the type.  For dev/local environments, skip downgrade.
        pass
    else:
        pass
