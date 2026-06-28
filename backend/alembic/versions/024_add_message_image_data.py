"""Add image_data column to messages table.

Revision ID: 024_add_message_image_data
Revises: 023_add_user_preference_counts
Create Date: 2026-06-27

Changes:
- Add ``image_data`` Text column to the ``messages`` table to store
  base64-encoded image data for user-uploaded photos in chat.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "024_add_message_image_data"
down_revision: Union[str, None] = "023_add_user_preference_counts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("image_data", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "image_data")
