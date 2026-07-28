"""drop account drive folder id

Revision ID: e215a6689507
Revises: 4458fb7299a5
Create Date: 2026-07-28 19:41:04.345095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e215a6689507'
down_revision: Union[str, Sequence[str], None] = '4458fb7299a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('accounts', 'drive_folder_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('accounts', sa.Column('drive_folder_id', sa.Text(), nullable=True))
