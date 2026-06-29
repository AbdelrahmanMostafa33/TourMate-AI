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


def upgrade() -> None:
    # PostgreSQL: Use ALTER TYPE ... ADD VALUE ... for enum
    # SQLite: Enums are stored as TEXT, so no schema change needed
    # MySQL: Use MODIFY COLUMN with new enum definition
    
    # For SQLite (current setup), enums are TEXT, so no migration needed
    # The Python enum change is sufficient
    pass


def downgrade() -> None:
    # For SQLite, no schema change to revert
    pass
