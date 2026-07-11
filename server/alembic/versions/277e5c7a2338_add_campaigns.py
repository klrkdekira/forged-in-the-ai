"""add campaigns

Revision ID: 277e5c7a2338
Revises: f4c386532138
Create Date: 2026-07-11 10:38:59.379656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '277e5c7a2338'
down_revision: Union[str, Sequence[str], None] = 'f4c386532138'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate also proposed dropping the srd_chunks* FTS5 tables: those
    # are raw SQL (f4c386532138), not SQLAlchemy models, so they're invisible
    # to AppBase.metadata and autogenerate wrongly reads that as "removed".
    # Left out here; they're untouched by this migration.
    op.create_table('campaigns',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('campaigns')
