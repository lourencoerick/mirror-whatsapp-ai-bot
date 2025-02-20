from datetime import datetime
from typing import Any
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func

from ..database import Base


class BaseModel(Base):
    """
    Classe base para todos os modelos.
    Inclui campos e métodos comuns a todas as tabelas.
    """

    __abstract__ = True

    # Campos comuns a todas as tabelas
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Gera nome da tabela automaticamente baseado no nome da classe.
        Example: UserMessage -> user_messages
        """
        return f"{cls.__name__.lower()}s"

    def to_dict(self) -> dict[str, Any]:
        """
        Converte o modelo para dicionário.
        Útil para serialização.
        """
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """
        Representação string do modelo.
        Útil para debugging.
        """
        attrs = ", ".join(f"{key}={value!r}" for key, value in self.to_dict().items())
        return f"{self.__class__.__name__}({attrs})"
