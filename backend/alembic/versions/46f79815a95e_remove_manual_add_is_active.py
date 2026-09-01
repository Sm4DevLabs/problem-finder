"""remove_manual_add_is_active

Revision ID: 46f79815a95e
Revises: 71e1a2a44326
Create Date: 2026-09-01 15:00:51.879056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46f79815a95e'
down_revision: Union[str, Sequence[str], None] = '71e1a2a44326'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Add is_active column (default True for existing sources)
    2. Remove MANUAL from collection_method enum
    3. Set any MANUAL sources to NULL collection_method and is_active = False
    """
    # Step 1: Add is_active column (default True)
    op.add_column('sources', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Step 2: Update sources with MANUAL method to NULL and mark inactive
    op.execute("""
        UPDATE sources
        SET collection_method = NULL, is_active = false
        WHERE collection_method = 'MANUAL'
    """)

    # Step 3: Recreate enum without MANUAL
    op.execute("ALTER TYPE collection_method_enum RENAME TO collection_method_enum_old")
    op.execute("CREATE TYPE collection_method_enum AS ENUM ('API', 'WEB_SCRAPING')")
    op.execute("""
        ALTER TABLE sources
        ALTER COLUMN collection_method TYPE collection_method_enum
        USING collection_method::text::collection_method_enum
    """)
    op.execute("DROP TYPE collection_method_enum_old")


def downgrade() -> None:
    """Reverse changes."""
    # Recreate old enum with MANUAL
    op.execute("ALTER TYPE collection_method_enum RENAME TO collection_method_enum_new")
    op.execute("CREATE TYPE collection_method_enum AS ENUM ('API', 'WEB_SCRAPING', 'MANUAL')")
    op.execute("""
        ALTER TABLE sources
        ALTER COLUMN collection_method TYPE collection_method_enum
        USING collection_method::text::collection_method_enum
    """)
    op.execute("DROP TYPE collection_method_enum_new")

    # Drop is_active column
    op.drop_column('sources', 'is_active')
