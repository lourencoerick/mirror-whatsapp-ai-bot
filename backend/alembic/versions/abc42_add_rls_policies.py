"""add rls policies

Revision ID: abc42
Revises: 4d3e94d2643c
Create Date: 2025-03-25 11:48:05.798310

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "abc42"
down_revision: str = "4d3e94d2643c"
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
        CREATE OR REPLACE FUNCTION current_account_id() RETURNS INTEGER AS $$
        BEGIN
            RETURN current_setting('my.app.account_id', true)::integer;
        END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    enable_rls_policy(
        "account_users",
        "account_users_policy",
        "user_id IN (SELECT id FROM users WHERE account_id = current_account_id())",
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
            "account_id = current_account_id()",
        )


def downgrade():
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
    op.execute("DROP FUNCTION IF EXISTS current_account_id()")
