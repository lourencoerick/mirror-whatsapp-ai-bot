import json
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from app.models.account import Account
from app.models.user import User
from app.models.inbox import Inbox
from app.models.contact import Contact
from models.contact_inbox import ContactInbox
from app.models.conversation import Conversation
from app.models.message import Message
from app.database import SessionLocal


def parse_datetime(value):
    if value:
        return datetime.fromisoformat(value)
    return None


def load_demo_data(db: Session, json_path: str):
    logger.info("[demo] Loading demo data from JSON...")
    with open(json_path, "r") as f:
        data = json.load(f)

    for record in data.get("accounts", []):
        db.merge(Account(**record))

    for record in data.get("users", []):
        db.merge(User(**record))

    for record in data.get("inboxes", []):
        db.merge(Inbox(**record))

    for record in data.get("contacts", []):
        db.merge(Contact(**record))

    for record in data.get("contact_inboxes", []):
        db.merge(ContactInbox(**record))

    for record in data.get("conversations", []):
        db.merge(Conversation(**record))

    for record in data.get("messages", []):
        record["sent_at"] = parse_datetime(record.get("sent_at"))
        db.merge(Message(**record))

    db.commit()
    logger.info("[demo] Demo data loaded successfully.")


if __name__ == "__main__":
    db: Session = SessionLocal()
    try:
        load_demo_data(db, "./data/demo_data.json")
    finally:
        db.close()
