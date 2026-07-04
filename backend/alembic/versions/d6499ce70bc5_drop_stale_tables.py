"""Drop stale tables that were renamed but never removed.

Revision ID: d6499ce70bc5
Revises: 029_add_ai_session_id
Create Date: 2026-07-03 21:38:31.752435+00:00

Context:
- Migration 015 renamed days -> itinerary_days, feedbacks -> feedback
  but the old tables were never dropped.
- This migration cleans up those stale, empty tables.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6499ce70bc5"
down_revision: Union[str, None] = "029_add_ai_session_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop stale indexes then tables ───────────────────────────────────────
    op.drop_index(op.f("ix_days_itinerary_id"), table_name="days")
    op.drop_table("days")

    op.drop_index(op.f("ix_feedbacks_trip_id"), table_name="feedbacks")
    op.drop_index(op.f("ix_feedbacks_user_id"), table_name="feedbacks")
    op.drop_table("feedbacks")


def downgrade() -> None:
    # ── Restore days table ──────────────────────────────────────────────────
    op.create_table(
        "days",
        sa.Column("day_id", sa.String(), primary_key=True),
        sa.Column("itinerary_id", sa.String(),
                  sa.ForeignKey("itineraries.itinerary_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("theme", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_days_itinerary_id"), "days", ["itinerary_id"])

    # ── Restore feedbacks table ─────────────────────────────────────────────
    op.create_table(
        "feedbacks",
        sa.Column("feedback_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(),
                  sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("trip_id", sa.String(),
                  sa.ForeignKey("trips.trip_id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("feedback_type", sa.Enum(
            "thumbs_up", "thumbs_down", "rating", "comment",
            name="feedback_type", create_type=False
        ), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(),
                  server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_feedbacks_user_id"), "feedbacks", ["user_id"])
    op.create_index(op.f("ix_feedbacks_trip_id"), "feedbacks", ["trip_id"])
