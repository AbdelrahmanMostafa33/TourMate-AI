"""Add ai_session_id column to conversations table for Redis session lookup.

Stores the active AI engine session_id for each conversation so that
on reconnection from chat history, the backend can pass it directly to
resume_or_create() for a fast Redis lookup instead of relying solely
on the recovery_state path.

Revision ID: 029_add_ai_session_id
Revises: 028_add_conversation_state_snapshot
Create Date: 2026-07-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "029_add_ai_session_id"
down_revision: Union[str, None] = "028_add_conversation_state_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "ai_session_id",
            sa.String,
            nullable=True,
            comment="Active AI engine session_id for this conversation — allows direct Redis lookup on reconnection",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "ai_session_id")
