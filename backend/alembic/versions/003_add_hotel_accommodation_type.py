"""Add accommodation_type to hotel_details table.

Revision ID: 003_add_hotel_accommodation_type
Revises: 002_erd_alignment
Create Date: 2026-06-20

Changes:
- Add accommodation_type column to hotel_details (String, nullable)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_add_hotel_accommodation_type"
down_revision: Union[str, None] = "002_erd_alignment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hotel_details",
        sa.Column("accommodation_type", sa.String, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hotel_details", "accommodation_type")
