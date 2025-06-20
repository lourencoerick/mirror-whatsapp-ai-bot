"""add scheduling user id

Revision ID: 223583cb0835
Revises: 64552f9e0591
Create Date: 2025-06-19 23:06:45.611460

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "223583cb0835"
down_revision: Union[str, None] = "64552f9e0591"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "company_profiles", sa.Column("scheduling_user_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        None,
        "company_profiles",
        "users",
        ["scheduling_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "company_profiles", type_="foreignkey")
    op.drop_column("company_profiles", "scheduling_user_id")
    # ### end Alembic commands ###
