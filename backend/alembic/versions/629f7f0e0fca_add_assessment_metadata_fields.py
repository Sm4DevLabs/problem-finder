"""add_assessment_metadata_fields

Revision ID: 629f7f0e0fca
Revises: 46b90f9a57f3
Create Date: 2026-09-01 12:57:38.271328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '629f7f0e0fca'
down_revision: Union[str, Sequence[str], None] = '46b90f9a57f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add assessment metadata and evidence fields to sources table."""
    # Add assessment metadata fields
    op.add_column('sources', sa.Column('assessment_reason', sa.Text(), nullable=True))
    op.add_column('sources', sa.Column('assessment_confidence', sa.Float(), nullable=True))
    op.add_column('sources', sa.Column('assessment_model', sa.String(length=100), nullable=True))
    op.add_column('sources', sa.Column('assessed_at', sa.DateTime(), nullable=True))

    # Add evidence-related fields
    op.add_column('sources', sa.Column('api_documentation_url', sa.String(length=500), nullable=True))
    op.add_column('sources', sa.Column('terms_url', sa.String(length=500), nullable=True))
    op.add_column('sources', sa.Column('robots_txt_url', sa.String(length=500), nullable=True))
    op.add_column('sources', sa.Column('github_repository_url', sa.String(length=500), nullable=True))
    op.add_column('sources', sa.Column('evidence_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove assessment metadata and evidence fields from sources table."""
    # Remove added columns
    op.drop_column('sources', 'evidence_summary')
    op.drop_column('sources', 'github_repository_url')
    op.drop_column('sources', 'robots_txt_url')
    op.drop_column('sources', 'terms_url')
    op.drop_column('sources', 'api_documentation_url')
    op.drop_column('sources', 'assessed_at')
    op.drop_column('sources', 'assessment_model')
    op.drop_column('sources', 'assessment_confidence')
    op.drop_column('sources', 'assessment_reason')
