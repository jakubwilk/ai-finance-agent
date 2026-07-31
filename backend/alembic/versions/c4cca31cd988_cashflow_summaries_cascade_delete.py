"""cashflow summaries cascade delete

Revision ID: c4cca31cd988
Revises: 3a350f20997d
Create Date: 2026-07-31 08:56:20.104854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4cca31cd988'
down_revision: Union[str, Sequence[str], None] = '3a350f20997d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        'cashflow_summaries_thread_id_fkey', 'cashflow_summaries', type_='foreignkey'
    )
    op.create_foreign_key(
        'cashflow_summaries_thread_id_fkey',
        'cashflow_summaries',
        'runs',
        ['thread_id'],
        ['thread_id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'cashflow_summaries_thread_id_fkey', 'cashflow_summaries', type_='foreignkey'
    )
    op.create_foreign_key(
        'cashflow_summaries_thread_id_fkey',
        'cashflow_summaries',
        'runs',
        ['thread_id'],
        ['thread_id'],
    )
