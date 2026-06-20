"""Fix schema drift: add price_level and accommodation_type columns.

Revision ID: 006_fix_schema_drift
Revises: 005_drop_orphaned_tables
Create Date: 2026-06-20

Changes:
- Add price_level (Integer) to places table (nullable, for price tier)
- Add accommodation_type (enum) to hotel_details table (nullable)
  Note: both columns already exist in the database from raw SQL fixes;
  this migration captures them for Alembic's version tracking.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "006_fix_schema_drift"
down_revision: Union[str, None] = "005_drop_orphaned_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Places: add price_level (IF NOT EXISTS) ──────────────────────────────
    op.execute(
        "ALTER TABLE places ADD COLUMN IF NOT EXISTS price_level INTEGER"
    )

    # ── Hotel details: add accommodation_type (IF NOT EXISTS) ─────────────────
    # The enum type 'accommodation_type' was already created in migration 004
    op.execute(
        "ALTER TABLE hotel_details ADD COLUMN IF NOT EXISTS accommodation_type accommodation_type"
    )


def downgrade() -> None:
    # ── Hotel details: drop accommodation_type ────────────────────────────────
    op.execute(
        "ALTER TABLE hotel_details DROP COLUMN IF EXISTS accommodation_type"
    )

    # ── Places: drop price_level ──────────────────────────────────────────────
    op.execute(
        "ALTER TABLE places DROP COLUMN IF EXISTS price_level"
    )
