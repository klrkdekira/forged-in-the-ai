"""baseline

Revision ID: b23423fbc34e
Revises: 
Create Date: 2026-07-10 16:34:46.017816

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'b23423fbc34e'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
