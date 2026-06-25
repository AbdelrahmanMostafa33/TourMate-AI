"""Migrate existing 'balanced' pace values to 'moderate' in trip_profiles.

Revision ID: 020_fix_balanced_pace_data
Revises: 019_add_candidate_pool_json
Create Date: 2026-06-26

Changes:
- Update all trip_profiles rows where pace = 'balanced' to pace = 'moderate'.

Why:
The AI engine's slot_normalizer maps 'balanced' → 'moderate' for new writes,
but existing rows in the database still have the old 'balanced' value.
The Python TripPace enum only allows 'packed', 'moderate', 'relaxed',
so loading any profile with pace='balanced' throws a LookupError:
  "'balanced' is not among the defined enum values.
   Enum name: trip_pace. Possible values: packed, moderate, relaxed"

This migration cleans up existing data so all reads succeed and the
Python enum stays in sync with what's stored in the database.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "020_fix_balanced_pace_data"
down_revision: Union[str, None] = "019_add_candidate_pool_json"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert existing 'balanced' rows to 'moderate'
    # 'balanced' exists as a PG enum value (from migration 017), so
    # the UPDATE is safe — it reads 'balanced' and writes 'moderate'.
    op.execute(
        "UPDATE trip_profiles "
        "SET pace = 'moderate' "
        "WHERE pace = 'balanced'"
    )


def downgrade() -> None:
    # No automatic downgrade — we cannot know which rows were originally
    # 'balanced' vs already 'moderate'.  Log a warning.
    import logging
    logging.warning(
        "[020] Cannot revert 'moderate' back to 'balanced'. "
        "After this migration, rows with pace='balanced' have been "
        "changed to 'moderate'. Downgrading would require knowing "
        "which rows were originally 'balanced', which is not tracked. "
        "Manual inspection may be needed."
    )
