"""add cashflow summaries table

Revision ID: 3a350f20997d
Revises: f0e0bc389b71
Create Date: 2026-07-30 11:09:02.661098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3a350f20997d'
down_revision: Union[str, Sequence[str], None] = 'f0e0bc389b71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cashflow_summaries',
        sa.Column('thread_id', sa.Text(), nullable=False),
        sa.Column('statement_id', sa.Text(), nullable=True),
        sa.Column('weekly', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'rolling_month', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            'fixed_costs_status',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['runs.thread_id']),
        sa.PrimaryKeyConstraint('thread_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cashflow_summaries')
