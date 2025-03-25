from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class InboxMember(BaseModel):
    __tablename__ = "inbox_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    __table_args__ = (
        Index("inbox_members_inbox_id_index", "inbox_id"),
        UniqueConstraint(
            "user_id", "inbox_id", name="inbox_members_user_id_inbox_id_unique"
        ),
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=False)

    user = relationship("User", back_populates="inbox_members")
    inbox = relationship("Inbox", back_populates="inbox_members")
