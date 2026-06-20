"""Change accommodation_type from String to enum.

Revision ID: 004_accommodation_type_enum
Revises: 003_add_hotel_accommodation_type
Create Date: 2026-06-20

Changes:
- Create accommodation_type enum (hotel, hostel, resort, luxury)
- Migrate existing String data to enum values (lowercase)
- Drop old String column and replace with enum column
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004_accommodation_type_enum"
down_revision: Union[str, None] = "003_add_hotel_accommodation_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    accommodation_type = sa.Enum(
        "hotel", "hostel", "resort", "luxury",
        name="accommodation_type",
    )
    accommodation_type.create(op.get_bind(), checkfirst=True)

    # Migrate data: lowercase existing values to match enum
    op.execute(
        "UPDATE hotel_details SET accommodation_type = LOWER(accommodation_type) "
        "WHERE accommodation_type IS NOT NULL"
    )

    # Drop old String column and recreate as enum
    op.drop_column("hotel_details", "accommodation_type")
    op.add_column(
        "hotel_details",
        sa.Column(
            "accommodation_type",
            sa.Enum(name="accommodation_type"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Drop enum column and restore as String
    op.drop_column("hotel_details", "accommodation_type")
    op.add_column(
        "hotel_details",
        sa.Column("accommodation_type", sa.String, nullable=True),
    )

    # Drop enum type
    sa.Enum(name="accommodation_type").drop(op.get_bind(), checkfirst=True)
