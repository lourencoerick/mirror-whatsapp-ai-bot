"""add initial status to inbox

Revision ID: 060f68470afd
Revises: 69337a530f3b
Create Date: 2025-04-17 23:10:57.088057

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "060f68470afd"
down_revision: Union[str, None] = "69337a530f3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("ALTER TYPE conversation_status_enum ADD VALUE IF NOT EXISTS 'BOT'")

    op.add_column(
        "inboxes",
        sa.Column(
            "initial_conversation_status",
            sa.Enum(
                "PENDING",
                "HUMAN_ACTIVE",
                "CLOSED",
                "OPEN",
                "BOT",
                name="conversation_status_enum",
            ),
            nullable=True,
            comment="Initial status of the conversation when created",
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("inboxes", "initial_conversation_status")
    # ### end Alembic commands ###
