"""Add card_data JSONB column to messages table for chat history card reconstruction.

Stores the exact structured card data (itinerary, hotel_options, flight_options,
booking_data) that was sent via WebSocket during the live chat, so that
chat history can reconstruct cards exactly as they appeared.

Revision ID: 027_add_card_data_column
Revises: 026_fix_trip_status_pg
Create Date: 2026-07-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "027_add_card_data_column"
down_revision: Union[str, None] = "026_fix_trip_status_pg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "card_data",
            postgresql.JSONB,
            nullable=True,
            comment="Structured card data: itinerary_data, hotel_options, flight_options, booking_data",
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "card_data")
