"""add_solution_fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-03 12:57:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add AI-generated solution classification fields."""
    op.add_column('source_items', sa.Column('solution_tags', sa.JSON(), nullable=True))
    op.add_column('source_items', sa.Column('solution_approach', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove solution classification fields."""
    op.drop_column('source_items', 'solution_approach')
    op.drop_column('source_items', 'solution_tags')
