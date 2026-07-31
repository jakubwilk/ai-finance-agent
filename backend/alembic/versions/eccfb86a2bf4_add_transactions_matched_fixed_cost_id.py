"""add transactions matched_fixed_cost_id

Revision ID: eccfb86a2bf4
Revises: 79554ef36e38
Create Date: 2026-07-29 09:06:59.324756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'eccfb86a2bf4'
down_revision: Union[str, Sequence[str], None] = '79554ef36e38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transactions',
        sa.Column('matched_fixed_cost_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'transactions_matched_fixed_cost_id_fkey',
        'transactions',
        'fixed_costs',
        ['matched_fixed_cost_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'transactions_matched_fixed_cost_id_fkey',
        'transactions',
        type_='foreignkey',
    )
    op.drop_column('transactions', 'matched_fixed_cost_id')
