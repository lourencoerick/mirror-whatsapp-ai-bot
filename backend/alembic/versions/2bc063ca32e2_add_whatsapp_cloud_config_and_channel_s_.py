"""Add whatsapp cloud config and channel s relationship with inboxes

Revision ID: 2bc063ca32e2
Revises: badbedcc38f2
Create Date: 2025-05-13 00:22:51.000109

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2bc063ca32e2"
down_revision: Union[str, None] = "badbedcc38f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the ENUM type details for 'channel_type_enum'
# These values will be the literal strings stored in the PostgreSQL ENUM type.
DB_ENUM_VALUES = ("whatsapp_evolution", "whatsapp_cloud", "simulation")
CHANNEL_TYPE_ENUM_NAME = "channel_type_enum"


def upgrade() -> None:
    # Step 1: Create the new ENUM type in the database
    # This ENUM will have uppercase values.
    db_channel_type_enum = postgresql.ENUM(*DB_ENUM_VALUES, name=CHANNEL_TYPE_ENUM_NAME)
    db_channel_type_enum.create(
        op.get_bind(), checkfirst=True
    )  # checkfirst=True avoids error if it already exists

    # --- Create whatsapp_cloud_configs table ---
    op.create_table(
        "whatsapp_cloud_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "phone_number_id",
            sa.String(length=255),
            nullable=False,
            comment="WhatsApp Cloud API Phone Number ID.",
        ),
        sa.Column(
            "waba_id",
            sa.String(length=255),
            nullable=False,
            comment="WhatsApp Business Account ID.",
        ),
        sa.Column(
            "encrypted_access_token",
            sa.LargeBinary(),
            nullable=False,
            comment="Encrypted System User Access Token (long-lived preferred) for WhatsApp Cloud API.",
        ),
        sa.Column(
            "webhook_verify_token",
            sa.String(length=255),
            nullable=True,
            comment="The verify token configured in the Meta App for webhook verification",
        ),  # Type changed to String, nullable=True
        sa.Column(
            "app_id",
            sa.String(length=255),
            nullable=True,
            comment="Meta App ID associated with the WhatsApp integration, if applicable.",
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_whatsapp_cloud_configs_account_id_accounts"),
            ondelete="CASCADE",
        ),  # Added constraint name
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_whatsapp_cloud_configs")
        ),  # Added constraint name
    )
    op.create_index(
        op.f("ix_whatsapp_cloud_configs_account_id"),
        "whatsapp_cloud_configs",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_cloud_configs_phone_number_id"),
        "whatsapp_cloud_configs",
        ["phone_number_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_whatsapp_cloud_configs_waba_id"),
        "whatsapp_cloud_configs",
        ["waba_id"],
        unique=False,
    )

    # --- Inbox table changes ---
    op.add_column(
        "inboxes",
        sa.Column(
            "evolution_instance_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column(
        "inboxes",
        sa.Column(
            "whatsapp_cloud_config_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )

    op.alter_column(
        "inboxes",
        "channel_id",
        existing_type=sa.VARCHAR(length=255),
        comment="Provider-specific ID for the channel (e.g., phone number ID, instance name).",  # Retaining comment update
        existing_nullable=False,
    )

    op.alter_column(
        "inboxes",
        "channel_type",
        existing_type=sa.VARCHAR(length=255),
        type_=db_channel_type_enum,  # Use the created ENUM type object
        existing_nullable=False,
        # Cast existing VARCHAR values to the new ENUM type.
        postgresql_using=f"LOWER(channel_type::text)::{CHANNEL_TYPE_ENUM_NAME}",
    )

    op.create_index(
        "ix_inbox_evolution_instance_id",
        "inboxes",
        ["evolution_instance_id"],
        unique=True,
    )
    op.create_index(
        "ix_inbox_whatsapp_cloud_config_id",
        "inboxes",
        ["whatsapp_cloud_config_id"],
        unique=True,
    )

    # The unique=True on create_index is generally sufficient for PostgreSQL.
    # Explicit unique constraints below might be redundant if unique indices serve the purpose.
    # If specific constraint names are needed, provide them. 'None' auto-generates names.
    op.create_unique_constraint(
        op.f("uq_inboxes_evolution_instance_id"), "inboxes", ["evolution_instance_id"]
    )  # Added constraint name
    op.create_unique_constraint(
        op.f("uq_inboxes_whatsapp_cloud_config_id"),
        "inboxes",
        ["whatsapp_cloud_config_id"],
    )  # Added constraint name

    op.create_foreign_key(
        "fk_inbox_evolution_instance_id",  # Name from your model is good
        "inboxes",
        "evolution_instances",
        ["evolution_instance_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_inbox_whatsapp_cloud_config_id",  # Name from your model is good
        "inboxes",
        "whatsapp_cloud_configs",
        ["whatsapp_cloud_config_id"],
        ["id"],
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - ADJUSTED ###

    # --- Revert Inbox table changes ---
    op.drop_constraint(
        "fk_inbox_whatsapp_cloud_config_id", "inboxes", type_="foreignkey"
    )
    op.drop_constraint("fk_inbox_evolution_instance_id", "inboxes", type_="foreignkey")

    op.drop_constraint(
        op.f("uq_inboxes_whatsapp_cloud_config_id"), "inboxes", type_="unique"
    )  # Use op.f() for consistency if names were auto-generated
    op.drop_constraint(
        op.f("uq_inboxes_evolution_instance_id"), "inboxes", type_="unique"
    )

    op.drop_index("ix_inbox_whatsapp_cloud_config_id", table_name="inboxes")
    op.drop_index("ix_inbox_evolution_instance_id", table_name="inboxes")

    # Define the enum object again for use in existing_type
    db_channel_type_enum_for_downgrade = postgresql.ENUM(
        *DB_ENUM_VALUES, name=CHANNEL_TYPE_ENUM_NAME
    )
    op.alter_column(
        "inboxes",
        "channel_type",
        existing_type=db_channel_type_enum_for_downgrade,
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
        postgresql_using="channel_type::text",  # Cast ENUM back to its text representation
    )

    op.alter_column(
        "inboxes",
        "channel_id",
        existing_type=sa.VARCHAR(length=255),
        comment=None,  # Remove comment
        existing_comment="Provider-specific ID for the channel (e.g., phone number ID, instance name).",
        existing_nullable=False,
    )
    op.drop_column("inboxes", "whatsapp_cloud_config_id")
    op.drop_column("inboxes", "evolution_instance_id")

    # --- Revert whatsapp_cloud_configs table ---
    op.drop_index(
        op.f("ix_whatsapp_cloud_configs_waba_id"), table_name="whatsapp_cloud_configs"
    )
    op.drop_index(
        op.f("ix_whatsapp_cloud_configs_phone_number_id"),
        table_name="whatsapp_cloud_configs",
    )
    op.drop_index(
        op.f("ix_whatsapp_cloud_configs_account_id"),
        table_name="whatsapp_cloud_configs",
    )
    op.drop_table("whatsapp_cloud_configs")

    # Step Last: Drop the ENUM type from the database
    db_channel_type_enum_for_downgrade.drop(
        op.get_bind(), checkfirst=True
    )  # checkfirst=True avoids error if it doesn't exist
    # ### end Alembic commands ###
