"""create_source_items_table

Revision ID: 97bed6de8eb3
Revises: 46f79815a95e
Create Date: 2026-09-02 10:04:16.902251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97bed6de8eb3'
down_revision: Union[str, Sequence[str], None] = '46f79815a95e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create source_items table for storing collected problems."""
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        'source_items',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=False),

        # Original data from source
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(500), nullable=True),

        # Enriched fields (AI-populated for sources that don't have them)
        sa.Column('problem_frequency', sa.Text(), nullable=True),
        sa.Column('existing_solutions', sa.Text(), nullable=True),
        sa.Column('pricing_estimate', sa.Text(), nullable=True),

        # Metadata
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_source_item_external_id'),
    )

    op.create_index('ix_source_items_source_id', 'source_items', ['source_id'])
    op.create_index('ix_source_items_fetched_at', 'source_items', ['fetched_at'])


def downgrade() -> None:
    """Drop source_items table."""
    op.drop_index('ix_source_items_fetched_at', 'source_items')
    op.drop_index('ix_source_items_source_id', 'source_items')
    op.drop_table('source_items')
