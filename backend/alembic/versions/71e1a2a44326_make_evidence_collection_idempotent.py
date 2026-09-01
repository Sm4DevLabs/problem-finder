"""make_evidence_collection_idempotent

Revision ID: 71e1a2a44326
Revises: f7e59c4984b2
Create Date: 2026-09-01 14:53:49.363551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71e1a2a44326'
down_revision: Union[str, Sequence[str], None] = 'f7e59c4984b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Make evidence collection idempotent:
    1. Delete duplicate evidence records (keep most recent)
    2. Add unique constraint on (source_id, evidence_type, url)
    """
    # Step 1: Delete duplicates, keeping only the most recent record
    op.execute("""
        DELETE FROM assessment_evidence
        WHERE id NOT IN (
            SELECT DISTINCT ON (source_id, evidence_type, url) id
            FROM assessment_evidence
            ORDER BY source_id, evidence_type, url, fetched_at DESC
        )
    """)

    # Step 2: Add unique constraint
    op.create_unique_constraint(
        'uq_source_evidence_url',
        'assessment_evidence',
        ['source_id', 'evidence_type', 'url']
    )


def downgrade() -> None:
    """Drop unique constraint."""
    op.drop_constraint('uq_source_evidence_url', 'assessment_evidence', type_='unique')
