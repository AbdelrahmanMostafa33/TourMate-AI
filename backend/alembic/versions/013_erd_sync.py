"""Sync database schema with final ERD.

Revision ID: 013_erd_sync
Revises: 010_remove_extra_model_fields
Create Date: 2026-06-23

Changes (supersedes removed 011 and 012):
- saved_places: add unique constraint on (user_id, place_id)
- trips:       drop traveler_group_type, budget columns
- trip_profiles: drop luxury_score, culture_score, adventure_score, confidence
- itinerary_stops: drop classification, importance_score, scheduled_time, user_notes
- Drop recommendations table entirely
- Drop unused ENUM types: traveler_group_type, stop_classification,
  recommendation_type, recommendation_status

Note: Migrations 011 (unique constraint) and 012 (pgvector) were removed.
Pgvector extension is not used — embedding remains as JSON.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "013_erd_sync"
down_revision: Union[str, None] = "010_remove_extra_model_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 0. saved_places: add unique constraint (from removed migration 011) ──
    op.execute("""
        DELETE FROM saved_places
        WHERE saved_place_id NOT IN (
            SELECT DISTINCT ON (user_id, place_id) saved_place_id
            FROM saved_places
            ORDER BY user_id, place_id, saved_at ASC
        )
    """)
    op.create_unique_constraint(
        "uq_saved_place_user_place",
        "saved_places",
        ["user_id", "place_id"],
    )

    # ── 1. trips: drop traveler_group_type and budget ─────────────────────────
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS traveler_group_type")
    op.execute("ALTER TABLE trips DROP COLUMN IF EXISTS budget")

    # ── 2. trip_profiles: drop scoring columns ────────────────────────────────
    op.execute("ALTER TABLE trip_profiles DROP COLUMN IF EXISTS luxury_score")
    op.execute("ALTER TABLE trip_profiles DROP COLUMN IF EXISTS culture_score")
    op.execute("ALTER TABLE trip_profiles DROP COLUMN IF EXISTS adventure_score")
    op.execute("ALTER TABLE trip_profiles DROP COLUMN IF EXISTS confidence")

    # ── 3. itinerary_stops: drop classification, importance_score, scheduled_time, user_notes ──
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS classification")
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS importance_score")
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS scheduled_time")
    op.execute("ALTER TABLE itinerary_stops DROP COLUMN IF EXISTS user_notes")

    # ── 4. Drop recommendations table ─────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS recommendations CASCADE")

    # ── 5. Drop unused ENUM types (only if no other columns reference them) ───
    # traveler_group_type — only used by trips.traveler_group_type (dropped above)
    op.execute("DROP TYPE IF EXISTS traveler_group_type")
    # stop_classification — only used by itinerary_stops.classification (dropped above)
    op.execute("DROP TYPE IF EXISTS stop_classification")
    # recommendation_type — only used by recommendations.recommendation_type (table dropped)
    op.execute("DROP TYPE IF EXISTS recommendation_type")
    # recommendation_status — only used by recommendations.status (table dropped)
    op.execute("DROP TYPE IF EXISTS recommendation_status")


def downgrade() -> None:
    # ── 6. Restore ENUM types ────────────────────────────────────────────────
    sa.Enum("solo", "couple", "family", "friends", "business",
            name="traveler_group_type").create(op.get_bind(), checkfirst=True)
    sa.Enum("must_see", "nice_to_have", "optional",
            name="stop_classification").create(op.get_bind(), checkfirst=True)
    sa.Enum("place", "activity", "restaurant", "hotel",
            name="recommendation_type").create(op.get_bind(), checkfirst=True)
    sa.Enum("pending", "accepted", "rejected", "expired",
            name="recommendation_status").create(op.get_bind(), checkfirst=True)

    # ── 5. Restore recommendations table ──────────────────────────────────────
    op.create_table(
        "recommendations",
        sa.Column("recommendation_id", sa.String, primary_key=True),
        sa.Column("trip_id", sa.String, sa.ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False),
        sa.Column("place_id", sa.String, sa.ForeignKey("places.place_id"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("recommendation_type", sa.Enum(
            "place", "activity", "restaurant", "hotel",
            name="recommendation_type"
        ), nullable=True),
        sa.Column("status", sa.Enum(
            "pending", "accepted", "rejected", "expired",
            name="recommendation_status"
        ), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_recommendations_trip_id", "recommendations", ["trip_id"])
    op.create_index("ix_recommendations_place_id", "recommendations", ["place_id"])

    # ── 4. itinerary_stops: restore columns ───────────────────────────────────
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS user_notes TEXT")
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS scheduled_time TIME")
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS importance_score INTEGER")
    op.execute("ALTER TABLE itinerary_stops ADD COLUMN IF NOT EXISTS classification stop_classification")

    # ── 3. trip_profiles: restore scoring columns ────────────────────────────
    op.execute("ALTER TABLE trip_profiles ADD COLUMN IF NOT EXISTS confidence FLOAT")
    op.execute("ALTER TABLE trip_profiles ADD COLUMN IF NOT EXISTS adventure_score FLOAT")
    op.execute("ALTER TABLE trip_profiles ADD COLUMN IF NOT EXISTS culture_score FLOAT")
    op.execute("ALTER TABLE trip_profiles ADD COLUMN IF NOT EXISTS luxury_score FLOAT")

    # ── 2. trips: restore traveler_group_type and budget ─────────────────────
    op.execute("ALTER TABLE trips ADD COLUMN IF NOT EXISTS budget FLOAT")
    op.execute("ALTER TABLE trips ADD COLUMN IF NOT EXISTS traveler_group_type traveler_group_type")

    # ── 1. saved_places: drop unique constraint (from removed migration 011) ─
    op.drop_constraint("uq_saved_place_user_place", "saved_places", type_="unique")
