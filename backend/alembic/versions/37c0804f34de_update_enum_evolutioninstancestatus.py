"""update enum EvolutionInstanceStatus

Revision ID: 37c0804f34de
Revises: 2b5899baa957
Create Date: 2025-04-11 20:04:58.151231

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "37c0804f34de"
down_revision: Union[str, None] = "2b5899baa957"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("ALTER TYPE evolutioninstancestatus ADD VALUE IF NOT EXISTS 'UNKNOWN'")
    op.execute(
        "ALTER TYPE evolutioninstancestatus ADD VALUE IF NOT EXISTS 'CONNECTING'"
    )
    op.execute("ALTER TYPE evolutioninstancestatus ADD VALUE IF NOT EXISTS 'API_ERROR'")

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
