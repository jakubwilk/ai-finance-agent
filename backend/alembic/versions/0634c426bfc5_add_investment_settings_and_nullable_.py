"""add investment_settings and nullable report_id

Revision ID: 0634c426bfc5
Revises: eccfb86a2bf4
Create Date: 2026-07-29 10:47:11.939613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0634c426bfc5'
down_revision: Union[str, Sequence[str], None] = 'eccfb86a2bf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'investment_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('risk_profile', sa.Text(), nullable=False),
        sa.Column('safety_buffer_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('instruments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "risk_profile IN ('conservative', 'balanced', 'aggressive')",
            name='ck_investment_settings_risk_profile',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column(
        'investment_recommendations', 'report_id', existing_type=sa.UUID(), nullable=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'investment_recommendations', 'report_id', existing_type=sa.UUID(), nullable=False
    )
    op.drop_table('investment_settings')
