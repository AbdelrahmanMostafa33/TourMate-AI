"""merge heads: fix_balanced_pace_data, user_preference_counts, review_likes_table

Revision ID: a62d661f5eaf
Revises: 020_fix_balanced_pace_data, 021_add_user_preference_counts, 021_add_review_likes_table
Create Date: 2026-06-27 20:02:54.541699+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a62d661f5eaf'
down_revision: Union[str, None] = ('020_fix_balanced_pace_data', '021_add_user_preference_counts', '021_add_review_likes_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
