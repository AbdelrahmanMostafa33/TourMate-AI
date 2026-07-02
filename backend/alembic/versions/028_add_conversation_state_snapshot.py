"""Add state_snapshot JSONB column to conversations table for Redis recovery.

Stores a lightweight snapshot of ConversationState (phase, slots, turn_count)
so the AI can recover structured state from PostgreSQL alone if Redis data
is lost or the session TTL expires.

Revision ID: 028_add_conversation_state_snapshot
Revises: 027_add_card_data_column
Create Date: 2026-07-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "028_add_conversation_state_snapshot"
down_revision: Union[str, None] = "027_add_card_data_column"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "state_snapshot",
            postgresql.JSONB,
            nullable=True,
            comment="Snapshot of ConversationState for recovery if Redis data is lost",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "state_snapshot")
