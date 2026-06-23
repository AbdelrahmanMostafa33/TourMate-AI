"""Fix itinerary_stops FK: days → itinerary_days

Revision ID: 016_fix_itinerary_stops_fk
Revises: 015_rename_tables_to_match_erd
Create Date: 2026-06-23

The old FK constraint ``itinerary_stops_day_id_fkey`` was created when the
parent table was still called ``days``.  After migration 015 renamed it to
``itinerary_days``, the FK was not automatically updated (depends on how
the constraint was originally created).  This migration drops the stale FK
and re-creates it pointing to ``itinerary_days.day_id``.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016_fix_itinerary_stops_fk"
down_revision: Union[str, None] = "015_rename_tables_to_match_erd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the stale FK that still references the old "days" table
    op.execute(
        "ALTER TABLE itinerary_stops "
        "DROP CONSTRAINT IF EXISTS itinerary_stops_day_id_fkey"
    )

    # Re-create FK pointing to the renamed table
    op.execute(
        "ALTER TABLE itinerary_stops "
        "ADD CONSTRAINT itinerary_stops_day_id_fkey "
        "FOREIGN KEY (day_id) REFERENCES itinerary_days (day_id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    # Revert to the old FK (for completeness)
    op.execute(
        "ALTER TABLE itinerary_stops "
        "DROP CONSTRAINT IF EXISTS itinerary_stops_day_id_fkey"
    )
    op.execute(
        "ALTER TABLE itinerary_stops "
        "ADD CONSTRAINT itinerary_stops_day_id_fkey "
        "FOREIGN KEY (day_id) REFERENCES days (day_id) ON DELETE CASCADE"
    )
