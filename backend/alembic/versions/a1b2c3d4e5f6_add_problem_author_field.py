"""add_problem_author_field

Revision ID: a1b2c3d4e5f6
Revises: 60dea9ee0fb9
Create Date: 2026-09-03 12:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '60dea9ee0fb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add problem_author field (Q5: Problem author)."""
    op.add_column('source_items', sa.Column('problem_author', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove problem_author field."""
    op.drop_column('source_items', 'problem_author')
