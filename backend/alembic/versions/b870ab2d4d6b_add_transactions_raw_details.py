"""add transactions raw_details

Revision ID: b870ab2d4d6b
Revises: 23df7ac4b4b4
Create Date: 2026-07-28 21:56:07.412831

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b870ab2d4d6b'
down_revision: Union[str, Sequence[str], None] = '23df7ac4b4b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transactions',
        sa.Column(
            'raw_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transactions', 'raw_details')
