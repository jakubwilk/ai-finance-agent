"""add runs table

Revision ID: f0e0bc389b71
Revises: 0634c426bfc5
Create Date: 2026-07-29 13:19:53.608936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0e0bc389b71'
down_revision: Union[str, Sequence[str], None] = '0634c426bfc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'runs',
        sa.Column('thread_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'waiting_for_review')",
            name='ck_runs_status',
        ),
        sa.PrimaryKeyConstraint('thread_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('runs')
