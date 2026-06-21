"""Add unique constraint on (user_id, place_id) for saved_places.

Revision ID: 011_add_saved_places_unique_constraint
Revises: 010_remove_extra_model_fields
Create Date: 2026-06-21

Changes:
- saved_places: deduplicate rows (keep oldest per user+place pair)
- saved_places: add unique constraint uq_saved_place_user_place on (user_id, place_id)
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_add_saved_places_unique_constraint"
down_revision: Union[str, None] = "010_remove_extra_model_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Deduplicate: keep the oldest saved_place per (user_id, place_id) ──────
    # If duplicates exist, the unique constraint would fail, so we remove
    # the newer rows first (keeping the one with the earliest saved_at).
    op.execute("""
        DELETE FROM saved_places
        WHERE saved_place_id NOT IN (
            SELECT DISTINCT ON (user_id, place_id) saved_place_id
            FROM saved_places
            ORDER BY user_id, place_id, saved_at ASC
        )
    """)

    # ── Add unique constraint ─────────────────────────────────────────────────
    op.create_unique_constraint(
        "uq_saved_place_user_place",
        "saved_places",
        ["user_id", "place_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_saved_place_user_place", "saved_places", type_="unique")
