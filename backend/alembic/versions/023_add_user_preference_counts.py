"""Add preference_counts JSON column to users table.

Revision ID: 023_add_user_preference_counts
Revises: 022_add_review_likes_table
Create Date: 2026-06-27

Changes:
- Add ``preference_counts`` JSON column to the ``users`` table to track
  how often each preference value has appeared across all of the user's
  approved trips.  This enables evidence-based persona updates that
  distinguish one-off choices from enduring preferences.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "023_add_user_preference_counts"
down_revision: Union[str, None] = "022_add_review_likes_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preference_counts", sa.JSON, nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column("users", "preference_counts")
