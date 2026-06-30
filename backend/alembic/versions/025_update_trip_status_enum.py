"""Update TripStatus enum with booking and payment states.

Revision ID: 025_update_trip_status_enum
Revises: 024_add_message_image_data
Create Date: 2026-06-29

Changes:
- Update TripStatus enum to include booking and payment workflow states:
  - planning (existing)
  - itinerary_draft (new)
  - awaiting_booking (new)
  - booking_pending (new)
  - payment_processing (new)
  - payment_failed (new)
  - booking_confirmed (new)
  - active (existing)
  - completed (existing)
- Removed: cancelled (trip cancellation handled at booking/payment level)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "025_update_trip_status_enum"
down_revision: Union[str, None] = "024_add_message_image_data"
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
        # PostgreSQL has a strict ENUM type. The initial migration (001)
        # created `trip_status` with only (planning, active, completed).
        # We must ALTER TYPE to add the new values one at a time.
        # `ADD VALUE IF NOT EXISTS` avoids errors if re-run.
        #
        # IMPORTANT: Use f-string interpolation (not bind parameters) because
        # ALTER TYPE ... ADD VALUE is DDL that doesn't support bound params.
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
        # PostgreSQL cannot easily remove a value from an enum.
        # The recommended approach is to create a new type, migrate
        # columns, drop the old type, and rename.
        # For now, we skip (downgrade is rarely needed for enum adds).
        pass
    else:
        pass
