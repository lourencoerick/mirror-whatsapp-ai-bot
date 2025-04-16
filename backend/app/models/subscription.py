import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Subscription(BaseModel):
    __tablename__ = "subscriptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    pricing_version = Column(String(255), nullable=True)
    expiry = Column(DateTime(timezone=True), nullable=True)
    billing_plan = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    state = Column(Integer, nullable=True)
    payment_source_added = Column(SmallInteger, nullable=True)

    account = relationship("Account", back_populates="subscriptions")
