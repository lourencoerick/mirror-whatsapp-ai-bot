"""Add company_profiles table

Revision ID: da3013a524cc
Revises: 060f68470afd
Create Date: 2025-04-19 01:07:00.617759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da3013a524cc'
down_revision: Union[str, None] = '060f68470afd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('company_profiles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('company_name', sa.String(), nullable=False),
    sa.Column('website', sa.String(), nullable=True),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('business_description', sa.Text(), nullable=False),
    sa.Column('target_audience', sa.String(), nullable=True),
    sa.Column('sales_tone', sa.String(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('communication_guidelines', sa.JSON(), nullable=False),
    sa.Column('ai_objective', sa.Text(), nullable=False),
    sa.Column('key_selling_points', sa.JSON(), nullable=False),
    sa.Column('offering_overview', sa.JSON(), nullable=False),
    sa.Column('delivery_options', sa.JSON(), nullable=False),
    sa.Column('opening_hours', sa.String(), nullable=True),
    sa.Column('fallback_contact_info', sa.String(), nullable=True),
    sa.Column('profile_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_profiles_account_id'), 'company_profiles', ['account_id'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_company_profiles_account_id'), table_name='company_profiles')
    op.drop_table('company_profiles')
    # ### end Alembic commands ###
