"""Install pgvector extension, migrate places.embedding to vector(768), add IVFFlat index.

Revision ID: 012_add_pgvector
Revises: 011_add_saved_places_unique_constraint
Create Date: 2026-06-22

Changes:
- Enable pgvector extension (CREATE EXTENSION IF NOT EXISTS vector)
- Change places.embedding column from JSON to vector(768)
  (existing JSON arrays are cast to vector, null/empty arrays become NULL)
- Create IVFFlat index on places.embedding using cosine distance
  (vector_cosine_ops) with 100 lists for efficient approximate search
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "012_add_pgvector"
down_revision: Union[str, None] = "011_add_saved_places_unique_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Enable pgvector extension ──────────────────────────────────────────
    # Requires superuser privileges; CREATE IF NOT EXISTS ensures idempotency.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 2. Migrate places.embedding from JSON → vector(768) ────────────────────
    # Existing data is either:
    #   - NULL → stays NULL
    #   - JSON array like [0.1, 0.2, ...] → cast via text → vector(768)
    #   - Empty array [] → converted to NULL
    op.execute("""
        ALTER TABLE places
        ALTER COLUMN embedding
        TYPE vector(768)
        USING CASE
            WHEN embedding IS NULL                THEN NULL
            WHEN embedding::text = '[]'           THEN NULL
            ELSE embedding::text::vector(768)
        END
    """)

    # ── 3. Create IVFFlat index for cosine similarity search ──────────────────
    # IVFFlat with 100 lists is a good default for up to ~100K rows.
    # The vector_cosine_ops operator class uses cosine distance (1 - cosine_similarity).
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_places_embedding
        ON places
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    # Drop the index
    op.execute("DROP INDEX IF EXISTS ix_places_embedding")

    # Revert column back to JSON
    op.execute("""
        ALTER TABLE places
        ALTER COLUMN embedding
        TYPE JSON
        USING CASE
            WHEN embedding IS NULL THEN NULL
            ELSE embedding::text::json
        END
    """)

    # Note: We do NOT drop the vector extension in downgrade because other
    # tables may depend on it. DROP EXTENSION IF EXISTS vector is commented out.
    # op.execute("DROP EXTENSION IF EXISTS vector")
