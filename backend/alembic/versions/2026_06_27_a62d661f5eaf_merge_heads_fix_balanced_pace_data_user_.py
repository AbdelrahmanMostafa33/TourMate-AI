"""continuation after 023_add_user_preference_counts

Revision ID: a62d661f5eaf
Revises: 023_add_user_preference_counts
Create Date: 2026-06-27 20:02:54.541699+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a62d661f5eaf'
down_revision: Union[str, None] = '023_add_user_preference_counts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
