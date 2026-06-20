"""Remove extra fields from models to match ERD.

Revision ID: 010_remove_extra_model_fields
Revises: 009_remove_attraction_tags
Create Date: 2026-06-20

Changes:
- restaurant_details: drop opening_hours column
- attraction_details: drop opening_hours column
- trips: drop preferences column
- images: drop user_id column and its FK/index
- itineraries: drop title column, drop total_estimated_cost column
- days: drop estimated_cost column
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "010_remove_extra_model_fields"
down_revision: Union[str, None] = "009_remove_attraction_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── restaurant_details: drop opening_hours ────────────────────────────────
    op.drop_column("restaurant_details", "opening_hours")

    # ── attraction_details: drop opening_hours ────────────────────────────────
    op.drop_column("attraction_details", "opening_hours")

    # ── trips: drop preferences ───────────────────────────────────────────────
    op.drop_column("trips", "preferences")

    # ── images: drop user_id ──────────────────────────────────────────────────
    op.drop_index("ix_images_user_id", table_name="images")
    op.drop_column("images", "user_id")

    # ── itineraries: drop title and total_estimated_cost ──────────────────────
    op.drop_column("itineraries", "title")
    op.drop_column("itineraries", "total_estimated_cost")

    # ── days: drop estimated_cost ─────────────────────────────────────────────
    op.drop_column("days", "estimated_cost")


def downgrade() -> None:
    # ── days: re-add estimated_cost ───────────────────────────────────────────
    op.add_column("days", sa.Column("estimated_cost", sa.Float, nullable=True))

    # ── itineraries: re-add title and total_estimated_cost ────────────────────
    op.add_column("itineraries", sa.Column("total_estimated_cost", sa.Float, nullable=True))
    op.add_column("itineraries", sa.Column("title", sa.String, nullable=True))

    # ── images: re-add user_id ────────────────────────────────────────────────
    op.add_column("images", sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False))
    op.create_index("ix_images_user_id", "images", ["user_id"])

    # ── trips: re-add preferences ─────────────────────────────────────────────
    op.add_column("trips", sa.Column("preferences", sa.JSON, nullable=True))

    # ── attraction_details: re-add opening_hours ──────────────────────────────
    op.add_column("attraction_details", sa.Column("opening_hours", sa.JSON, nullable=True))

    # ── restaurant_details: re-add opening_hours ──────────────────────────────
    op.add_column("restaurant_details", sa.Column("opening_hours", sa.JSON, nullable=True))
