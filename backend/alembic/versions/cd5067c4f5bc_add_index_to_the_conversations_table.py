"""add index to the conversations table

Revision ID: cd5067c4f5bc
Revises: b84c69aae1a6
Create Date: 2025-04-03 23:19:56.009524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd5067c4f5bc'
down_revision: Union[str, None] = 'b84c69aae1a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('idx_conversations_inbox_id', 'conversations', ['inbox_id'], unique=False)
    op.create_index('idx_conversations_last_message_at', 'conversations', ['last_message_at'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_conversations_last_message_at', table_name='conversations')
    op.drop_index('idx_conversations_inbox_id', table_name='conversations')
    # ### end Alembic commands ###
