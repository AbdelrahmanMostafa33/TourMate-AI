"""Add 'flight' to booking_type and 'amadeus' to booking_provider enums.

Revision ID: 021_add_flight_amadeus_enums
Revises: 020_fix_balanced_pace_data
Create Date: 2026-06-25

Changes:
- Add 'flight' to the booking_type ENUM type
- Add 'amadeus' to the booking_provider ENUM type

These values are needed for the Amadeus flight booking simulation feature,
which reuses the existing Booking table with booking_type='flight' and
provider='amadeus'.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "021_add_flight_amadeus_enums"
down_revision: Union[str, None] = "020_fix_balanced_pace_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    # PostgreSQL 9.3+ allows adding values but the statement is not
    # transactional, so we execute outside the Alembic transaction.
    op.execute("ALTER TYPE booking_type ADD VALUE IF NOT EXISTS 'flight'")
    op.execute("ALTER TYPE booking_provider ADD VALUE IF NOT EXISTS 'amadeus'")


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an ENUM type.
    # The only way to "downgrade" would be to create a new type without
    # 'flight'/'amadeus', alter the column, and drop the old type — too
    # destructive to automate. Log a warning instead.
    import logging  # noqa: F811
    logging.warning(
        "[020] Cannot remove 'flight' from booking_type or 'amadeus' from "
        "booking_provider ENUMs. PostgreSQL does not support "
        "ALTER TYPE ... DROP VALUE. Manual intervention required if "
        "downgrade is needed."
    )
