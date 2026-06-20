"""Remove tags column from attraction_details.

Revision ID: 009_remove_attraction_tags
Revises: 008_fix_remaining_drift
Create Date: 2026-06-20

Changes:
- Drop tags (JSON) column from attraction_details table
  per updated ERD and data schema (tags removed from class diagram).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "009_remove_attraction_tags"
down_revision: Union[str, None] = "008_fix_remaining_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("attraction_details", "tags")


def downgrade() -> None:
    op.add_column("attraction_details", sa.Column("tags", sa.JSON, nullable=True))
