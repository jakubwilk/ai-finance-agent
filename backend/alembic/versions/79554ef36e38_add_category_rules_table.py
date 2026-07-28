"""add category_rules table

Revision ID: 79554ef36e38
Revises: b870ab2d4d6b
Create Date: 2026-07-29 00:59:37.190192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79554ef36e38'
down_revision: Union[str, Sequence[str], None] = 'b870ab2d4d6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'category_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('match_key', sa.Text(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_key', name='uq_category_rules_match_key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('category_rules')
