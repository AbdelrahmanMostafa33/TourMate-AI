"""Rename tables to match ERD: feedbacks→feedback, days→itinerary_days.

Revision ID: 015_rename_tables_to_match_erd
Revises: 014_drop_orphan_profile_cols
Create Date: 2026-06-23

Changes:
- Rename "feedbacks" → "feedback"
- Rename "days" → "itinerary_days"
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "015_rename_tables_to_match_erd"
down_revision: Union[str, None] = "014_drop_orphan_profile_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Rename feedbacks → feedback ─────────────────────────────────────────
    op.rename_table("feedbacks", "feedback")

    # ── Rename days → itinerary_days ────────────────────────────────────────
    op.rename_table("days", "itinerary_days")


def downgrade() -> None:
    # ── Revert itinerary_days → days ────────────────────────────────────────
    op.rename_table("itinerary_days", "days")

    # ── Revert feedback → feedbacks ──────────────────────────────────────────
    op.rename_table("feedback", "feedbacks")
