from datetime import datetime
from typing import Any
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func

from app.database import Base


class BaseModel(Base):
    """
    Base class for all models.
    Includes common fields and methods for all tables.
    """

    __abstract__ = True

    # Common fields for all tables
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Generates table name automatically based on the class name.
        Example: UserMessage -> user_messages
        """
        return f"{cls.__name__.lower()}s"

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


class TestModel(BaseModel):
    """
    Simple model for database testing.
    """

    __tablename__ = "test_models"  # Explicit table name

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    value = Column(Integer, nullable=True)
