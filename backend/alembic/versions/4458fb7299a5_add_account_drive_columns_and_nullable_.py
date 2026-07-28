"""add account drive columns and nullable statement balances

Revision ID: 4458fb7299a5
Revises: 9d0d806b066e
Create Date: 2026-07-28 15:15:54.354928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4458fb7299a5'
down_revision: Union[str, Sequence[str], None] = '9d0d806b066e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('drive_folder_id', sa.Text(), nullable=True))
    op.add_column(
        'accounts',
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        'statements', 'period_start', existing_type=sa.Date(), nullable=True
    )
    op.alter_column(
        'statements', 'period_end', existing_type=sa.Date(), nullable=True
    )
    op.alter_column(
        'statements',
        'opening_balance',
        existing_type=sa.Numeric(14, 2),
        nullable=True,
    )
    op.alter_column(
        'statements',
        'closing_balance',
        existing_type=sa.Numeric(14, 2),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'statements',
        'closing_balance',
        existing_type=sa.Numeric(14, 2),
        nullable=False,
    )
    op.alter_column(
        'statements',
        'opening_balance',
        existing_type=sa.Numeric(14, 2),
        nullable=False,
    )
    op.alter_column(
        'statements', 'period_end', existing_type=sa.Date(), nullable=False
    )
    op.alter_column(
        'statements', 'period_start', existing_type=sa.Date(), nullable=False
    )
    op.drop_column('accounts', 'last_synced_at')
    op.drop_column('accounts', 'drive_folder_id')
