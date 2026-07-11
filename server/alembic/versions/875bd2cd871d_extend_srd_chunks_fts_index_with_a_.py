"""extend srd chunks fts index with a source column

Revision ID: 875bd2cd871d
Revises: 277e5c7a2338
Create Date: 2026-07-11 15:00:09.992901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '875bd2cd871d'
down_revision: Union[str, Sequence[str], None] = '277e5c7a2338'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """FR-24: module prose joins the SRD in the same retrieval corpus, so
    one BM25 query ranks across both rather than merging two separately-
    scored result sets. FTS5 virtual tables in this SQLite build refuse
    `ALTER TABLE ... ADD COLUMN` ("virtual tables may not be altered"),
    so this drops and recreates rather than altering in place - safe
    since the table is a derived cache (`make index-srd`/re-saving a
    module repopulates it), never a source of truth."""
    op.execute("DROP TABLE srd_chunks")
    op.execute(
        "CREATE VIRTUAL TABLE srd_chunks USING fts5("
        "heading, level UNINDEXED, line UNINDEXED, source UNINDEXED, body"
        ")"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE srd_chunks")
    op.execute(
        "CREATE VIRTUAL TABLE srd_chunks USING fts5("
        "heading, level UNINDEXED, line UNINDEXED, body"
        ")"
    )
