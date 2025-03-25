from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import Connection, Transaction

from loguru import logger
from app.middleware.account_context import get_account_id


@event.listens_for(Session, "after_begin")
def set_rls_context(
    session: Session, transaction: Transaction, connection: Connection
) -> None:
    """
    Listener that injects the current account_id into the PostgreSQL session
    for use with Row-Level Security (RLS).
    """
    try:
        account_id: int = get_account_id()
        connection.execute(text(f"SET LOCAL my.app.account_id = {account_id}"))
        logger.debug(f"[RLS] SET LOCAL my.app.account_id = {account_id}")
    except RuntimeError:
        logger.warning("[RLS] No account_id in context – skipping SET LOCAL")
    except Exception as e:
        logger.exception(f"[RLS] Failed to set account_id: {e}")
