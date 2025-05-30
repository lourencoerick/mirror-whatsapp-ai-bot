"""remove is_active flag

Revision ID: 0743fb99ca00
Revises: ba37a54084f6
Create Date: 2025-04-26 20:42:07.628755

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0743fb99ca00'
down_revision: Union[str, None] = 'ba37a54084f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_bot_agents_is_active', table_name='bot_agents')
    op.drop_column('bot_agents', 'is_active')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('bot_agents', sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=False))
    op.create_index('ix_bot_agents_is_active', 'bot_agents', ['is_active'], unique=False)
    # ### end Alembic commands ###
