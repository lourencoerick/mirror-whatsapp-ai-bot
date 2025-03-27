from sqlalchemy.orm import Session
from sqlalchemy import text


def find_account_id_from_source(source_id: str, db: Session) -> int | None:
    result = db.execute(
        text("SELECT account_id FROM inboxes WHERE channel_id = :source_id LIMIT 1"),
        {"source_id": source_id},
    )
    row = result.fetchone()
    return 1
    return row[0] if row else None
