"""Drop orphaned shopping_score and family_score from trip_profiles.

Revision ID: 014_drop_orphaned_profile_columns
Revises: 013_erd_sync
Create Date: 2026-06-23

Changes:
- trip_profiles: drop shopping_score and family_score columns
  that were missed in migration 013_erd_sync.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "014_drop_orphaned_profile_columns"
down_revision: Union[str, None] = "013_erd_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE trip_profiles DROP COLUMN IF EXISTS shopping_score")
    op.execute("ALTER TABLE trip_profiles DROP COLUMN IF EXISTS family_score")


def downgrade() -> None:
    op.execute("ALTER TABLE trip_profiles ADD COLUMN IF NOT EXISTS shopping_score FLOAT")
    op.execute("ALTER TABLE trip_profiles ADD COLUMN IF NOT EXISTS family_score FLOAT")
