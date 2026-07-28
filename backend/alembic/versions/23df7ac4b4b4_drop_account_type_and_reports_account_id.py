"""drop account_type and reports account_id

Revision ID: 23df7ac4b4b4
Revises: e215a6689507
Create Date: 2026-07-28 19:52:30.121054

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23df7ac4b4b4'
down_revision: Union[str, Sequence[str], None] = 'e215a6689507'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('reports_account_id_fkey', 'reports', type_='foreignkey')
    op.drop_column('reports', 'account_id')
    op.drop_constraint('uq_accounts_account_type', 'accounts', type_='unique')
    op.drop_constraint('ck_accounts_account_type', 'accounts', type_='check')
    op.drop_column('accounts', 'account_type')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'accounts',
        sa.Column(
            'account_type', sa.Text(), nullable=False, server_default='private'
        ),
    )
    op.create_check_constraint(
        'ck_accounts_account_type', 'accounts', "account_type IN ('private', 'company')"
    )
    op.create_unique_constraint(
        'uq_accounts_account_type', 'accounts', ['account_type']
    )
    op.add_column('reports', sa.Column('account_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'reports_account_id_fkey', 'reports', 'accounts', ['account_id'], ['id']
    )
