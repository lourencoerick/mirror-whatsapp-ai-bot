"""Add RLS policies for multi-tenant tables

Revision ID: abc42
Revises: 3e44287f6054
Create Date: 2025-02-20 23:13:07.123456

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "abc42"
down_revision: str = "3e44287f6054"
branch_labels = None
depends_on = None


def enable_rls_policy(table: str, policy: str, condition: str):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"CREATE POLICY {policy} ON {table} FOR SELECT USING ({condition});")


def disable_rls_policy(table: str, policy: str):
    op.execute(f"DROP POLICY {policy} ON {table};")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def upgrade():

    op.execute(
        """
        CREATE OR REPLACE FUNCTION current_user_id() RETURNS INTEGER AS $$
        BEGIN
            RETURN current_setting('app.current_user', true)::integer;
        END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    enable_rls_policy(
        "account_users", "account_users_policy", "user_id = current_user_id()"
    )

    common_tables = [
        "contacts",
        "conversations",
        "inboxes",
        "messages",
        "subscriptions",
        "webhooks",
        "events",
        "agent_bot_inboxes",
    ]

    for table in common_tables:
        enable_rls_policy(
            table,
            f"{table}_policy",
            "account_id IN (SELECT account_id FROM account_users WHERE user_id = current_user_id())",
        )


def downgrade():
    # Removendo as políticas em ordem reversa
    common_tables = [
        "agent_bot_inboxes",
        "events",
        "webhooks",
        "subscriptions",
        "messages",
        "inboxes",
        "conversations",
        "contacts",
    ]

    for table in common_tables:
        disable_rls_policy(table, f"{table}_policy")

    disable_rls_policy("account_users", "account_users_policy")
