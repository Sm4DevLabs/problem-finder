"""create_assessment_evidence_table

Revision ID: f7e59c4984b2
Revises: 629f7f0e0fca
Create Date: 2026-09-01 14:04:56.946322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7e59c4984b2'
down_revision: Union[str, Sequence[str], None] = '629f7f0e0fca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create assessment_evidence table for storing fetched evidence."""
    op.create_table(
        'assessment_evidence',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_id', sa.UUID(), nullable=False),
        sa.Column('evidence_type', sa.String(length=50), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('content_excerpt', sa.Text(), nullable=True),
        sa.Column('fetch_status', sa.String(length=20), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
    )

    # Add indexes for common queries
    op.create_index('ix_assessment_evidence_source_id', 'assessment_evidence', ['source_id'])
    op.create_index('ix_assessment_evidence_evidence_type', 'assessment_evidence', ['evidence_type'])


def downgrade() -> None:
    """Drop assessment_evidence table."""
    op.drop_index('ix_assessment_evidence_evidence_type')
    op.drop_index('ix_assessment_evidence_source_id')
    op.drop_table('assessment_evidence')
