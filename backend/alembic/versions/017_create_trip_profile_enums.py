"""Create enum types for trip_profiles and alter columns to use them.

Revision ID: 017_create_trip_profile_enums
Revises: 016_fix_itinerary_stops_fk
Create Date: 2026-06-24

Changes:
- Create PostgreSQL ENUM types: budget_level, travel_style, trip_pace
  (matching the Python enum classes BudgetLevel, TravelStyle, TripPace)
- Alter trip_profiles.budget_level from VARCHAR → budget_level ENUM
- Alter trip_profiles.travel_style from VARCHAR → travel_style ENUM
- Alter trip_profiles.pace from VARCHAR → trip_pace ENUM

Why:
The SQLAlchemy model (profile.py) defines these columns as SAEnum but
without an explicit name= parameter. SQLAlchemy then auto-generates the
PostgreSQL type name from the Python class name (lowercased):
  BudgetLevel → "budgetlevel"
  TravelStyle → "travelstyle"
  TripPace    → "trippace"

But the database already has enum types with underscores:
  "budget_level", "travel_style", "trip_pace"

This migration ensures the PostgreSQL enum types exist with the correct
underscored names and alters the columns to use them, matching what the
model now references via name="budget_level" etc.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "017_create_trip_profile_enums"
down_revision: Union[str, None] = "016_fix_itinerary_stops_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create ENUM types (if they don't already exist) ──────────────────
    budget_level_enum = sa.Enum(
        "budget", "moderate", "luxury",
        name="budget_level",
    )
    budget_level_enum.create(op.get_bind(), checkfirst=True)

    travel_style_enum = sa.Enum(
        "romantic", "adventure", "family", "business", "solo",
        "cultural", "relaxation",
        name="travel_style",
    )
    travel_style_enum.create(op.get_bind(), checkfirst=True)

    trip_pace_enum = sa.Enum(
        "packed", "balanced", "moderate", "relaxed",
        name="trip_pace",
    )
    trip_pace_enum.create(op.get_bind(), checkfirst=True)

    # ── 2. Alter columns from VARCHAR → ENUM ────────────────────────────────
    # Using raw SQL because the columns may currently be VARCHAR (from
    # migration 002) or may already be a differently-named enum type.

    # budget_level: VARCHAR → budget_level ENUM
    op.execute(
        "ALTER TABLE trip_profiles "
        "ALTER COLUMN budget_level TYPE budget_level "
        "USING budget_level::text::budget_level"
    )

    # travel_style: VARCHAR → travel_style ENUM
    op.execute(
        "ALTER TABLE trip_profiles "
        "ALTER COLUMN travel_style TYPE travel_style "
        "USING travel_style::text::travel_style"
    )

    # pace: VARCHAR → trip_pace ENUM
    op.execute(
        "ALTER TABLE trip_profiles "
        "ALTER COLUMN pace TYPE trip_pace "
        "USING pace::text::trip_pace"
    )

    # ── 3. Drop old auto-generated enum types if they exist (safe to ignore) ─
    # These were created by SQLAlchemy's SAEnum without an explicit name:
    #   "budgetlevel", "travelstyle", "trippace"
    # They may or may not exist depending on whether create_all() was ever
    # called. Drop them only if present and not referenced by any column.
    for old_type in ("budgetlevel", "travelstyle", "trippace"):
        op.execute(f"DROP TYPE IF EXISTS {old_type}")


def downgrade() -> None:
    # ── 1. Revert columns back to VARCHAR ────────────────────────────────────
    op.execute(
        "ALTER TABLE trip_profiles "
        "ALTER COLUMN budget_level TYPE VARCHAR "
        "USING budget_level::text"
    )
    op.execute(
        "ALTER TABLE trip_profiles "
        "ALTER COLUMN travel_style TYPE VARCHAR "
        "USING travel_style::text"
    )
    op.execute(
        "ALTER TABLE trip_profiles "
        "ALTER COLUMN pace TYPE VARCHAR "
        "USING pace::text"
    )

    # ── 2. Drop the ENUM types ───────────────────────────────────────────────
    sa.Enum(name="budget_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="travel_style").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="trip_pace").drop(op.get_bind(), checkfirst=True)
