import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Any
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func

from app.database import Base


class BaseModel(Base):
    """
    Base class for all models.
    Includes common fields and methods for all tables.
    """

    __abstract__ = True

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Generates table name automatically based on the class name.
        Example: UserMessage -> user_messages
        """
        return f"{cls.__name__.lower()}s"

    # Common fields for all tables
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Converts the model to a dictionary.
        Useful for serialization.
        """
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """
        String representation of the model.
        Useful for debugging.
        """
        attrs = ", ".join(f"{key}={value!r}" for key, value in self.to_dict().items())
        return f"{self.__class__.__name__}({attrs})"
