"""Add 'moderate' to trip_pace ENUM type.

Revision ID: 018_add_moderate_to_trip_pace
Revises: 017_create_trip_profile_enums
Create Date: 2026-06-24

Changes:
- Add 'moderate' to the trip_pace ENUM type so the AI engine's canonical
  pace value "moderate" is accepted by the database.

Why:
The AI engine (slot_normalizer) normalizes pace to one of:
  'relaxed', 'moderate', 'packed'
But the trip_pace ENUM only had 'packed', 'balanced', 'relaxed'.
This caused a LookupError when the service layer tried to store 'moderate'
into the ENUM column.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "018_add_moderate_to_trip_pace"
down_revision: Union[str, None] = "017_create_trip_profile_enums"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL ALTER TYPE ... ADD VALUE cannot be run inside a transaction
    # block.  Alembic runs migrations in a transaction by default, so we
    # use op.execute() with an explicit commit workaround.
    op.execute("ALTER TYPE trip_pace ADD VALUE IF NOT EXISTS 'moderate' BEFORE 'relaxed'")


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an ENUM type.
    # The only way to "downgrade" would be to create a new type without
    # 'moderate', alter the column, and drop the old type — too destructive
    # to automate.  Log a warning instead.
    import logging
    logging.warning(
        "[018] Cannot remove 'moderate' from trip_pace ENUM. "
        "PostgreSQL does not support ALTER TYPE ... DROP VALUE. "
        "Manual intervention required if downgrade is needed."
    )
