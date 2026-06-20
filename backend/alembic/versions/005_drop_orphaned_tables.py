"""Drop orphaned behavioral_profiles and quizzes tables.

Revision ID: 005_drop_orphaned_tables
Revises: 004_accommodation_type_enum
Create Date: 2026-06-20

Changes:
- Drop quizzes table (replaced by trip_profiles in migration 002)
- Drop behavioral_profiles table (replaced by trip_profiles in migration 002)

These tables were created in 001_initial_schema and were supposed to be
dropped in 002_erd_alignment, but they still exist in the database.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "005_drop_orphaned_tables"
down_revision: Union[str, None] = "004_accommodation_type_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop quizzes (IF EXISTS for idempotency) ─────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_quizzes_user_id")
    op.execute("DROP TABLE IF EXISTS quizzes")

    # ── Drop behavioral_profiles (IF EXISTS for idempotency) ─────────────────
    op.execute("DROP INDEX IF EXISTS ix_behavioral_profiles_user_id")
    op.execute("DROP TABLE IF EXISTS behavioral_profiles")


def downgrade() -> None:
    # ── Recreate behavioral_profiles ──────────────────────────────────────────
    op.create_table(
        "behavioral_profiles",
        sa.Column("profile_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False, unique=True),
        sa.Column("pace_style", sa.String, nullable=True),
        sa.Column("spending_style", sa.String, nullable=True),
        sa.Column("experience_lean", sa.String, nullable=True),
        sa.Column("day_rhythm", sa.String, nullable=True),
        sa.Column("attraction_preference", sa.String, nullable=True),
        sa.Column("social_style", sa.String, nullable=True),
        sa.Column("interests", JSON, nullable=True),
        sa.Column("dining_preferences", JSON, nullable=True),
        sa.Column("accommodation_preferences", JSON, nullable=True),
        sa.Column("custom_interests", JSON, nullable=True),
        sa.Column("persona_title", sa.String, nullable=True),
        sa.Column("persona_summary", sa.Text, nullable=True),
        sa.Column("quiz_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_behavioral_profiles_user_id", "behavioral_profiles", ["user_id"], unique=True)

    # ── Recreate quizzes ──────────────────────────────────────────────────────
    op.create_table(
        "quizzes",
        sa.Column("quiz_id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("answers", JSON, nullable=True),
        sa.Column("is_completed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])
