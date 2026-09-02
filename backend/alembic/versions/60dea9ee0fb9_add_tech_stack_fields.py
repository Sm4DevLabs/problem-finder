"""add_tech_stack_fields

Revision ID: 60dea9ee0fb9
Revises: 97bed6de8eb3
Create Date: 2026-09-02 10:06:15.709252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60dea9ee0fb9'
down_revision: Union[str, Sequence[str], None] = '97bed6de8eb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tech stack recommendation fields."""
    op.add_column('source_items', sa.Column('tech_stack_options', sa.JSON(), nullable=True))
    op.add_column('source_items', sa.Column('recommended_tech_stack', sa.JSON(), nullable=True))
    op.add_column('source_items', sa.Column('tech_stack_justification', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove tech stack fields."""
    op.drop_column('source_items', 'tech_stack_justification')
    op.drop_column('source_items', 'recommended_tech_stack')
    op.drop_column('source_items', 'tech_stack_options')
