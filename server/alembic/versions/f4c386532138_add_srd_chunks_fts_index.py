"""add srd chunks fts index

Revision ID: f4c386532138
Revises: e38e1b2df840
Create Date: 2026-07-10 21:49:46.171264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4c386532138'
down_revision: Union[str, Sequence[str], None] = 'e38e1b2df840'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """FR-13/ADR-0003: a lexical (BM25) retrieval index over SRD chunks.
    An FTS5 virtual table isn't a normal SQLAlchemy-mapped table, so this
    is raw SQL rather than autogenerate/op.create_table; `level` and
    `line` are UNINDEXED (metadata to return, not to search)."""
    op.execute(
        "CREATE VIRTUAL TABLE srd_chunks USING fts5("
        "heading, level UNINDEXED, line UNINDEXED, body"
        ")"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE srd_chunks")
