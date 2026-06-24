"""Add candidate_pool_json to itineraries for persistent edit pools.

Revision ID: 019_add_candidate_pool_json
Revises: 018_add_moderate_to_trip_pace
Create Date: 2026-06-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "019_add_candidate_pool_json"
down_revision: Union[str, None] = "018_add_moderate_to_trip_pace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "itineraries",
        sa.Column("candidate_pool_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("itineraries", "candidate_pool_json")
