from sqlalchemy import Column, Integer, String, DateTime, SmallInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Subscription(BaseModel):
    __tablename__ = "subscriptions"
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    pricing_version = Column(String(255), nullable=True)
    expiry = Column(DateTime, nullable=True)
    billing_plan = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    state = Column(Integer, nullable=True)
    payment_source_added = Column(SmallInteger, nullable=True)

    account = relationship("Account", back_populates="subscriptions")
