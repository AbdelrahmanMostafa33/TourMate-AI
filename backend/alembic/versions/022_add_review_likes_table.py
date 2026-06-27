"""Add review_likes table for tracking user review likes.

Revision ID: 022_add_review_likes_table
Revises: 021_add_flight_amadeus_enums
Create Date: 2026-06-27

Changes:
- Create review_likes table with composite PK (user_id, review_id)
- Add FK references to users and reviews
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "022_add_review_likes_table"
down_revision: Union[str, None] = "021_add_flight_amadeus_enums"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_likes",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("review_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"],
            name="fk_review_likes_user",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["reviews.review_id"],
            ondelete="CASCADE",
            name="fk_review_likes_review",
        ),
        sa.PrimaryKeyConstraint("user_id", "review_id", name="pk_review_likes"),
    )
    op.create_index(
        "ix_review_likes_review_id", "review_likes", ["review_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_likes_review_id", table_name="review_likes")
    op.drop_table("review_likes")
