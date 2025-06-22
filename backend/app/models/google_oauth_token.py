# backend/app/models/google_oauth_token.py

import uuid
from sqlalchemy import (
    Column,
    ForeignKey,
    JSON,
    LargeBinary,  # Usado para armazenar dados binários, como tokens criptografados
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped

from app.models.base import BaseModel


class GoogleOAuthToken(BaseModel):
    """
    SQLAlchemy model for securely storing Google OAuth refresh tokens for users.
    """

    __tablename__ = "google_oauth_tokens"

    id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the token record.",
    )

    # Chave estrangeira para o nosso modelo User.
    # Cada usuário pode ter no máximo um token do Google armazenado.
    user_id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Garante a relação 1:1 entre User e GoogleOAuthToken
        index=True,
        doc="Foreign key linking to the user who granted the permission.",
    )

    # Armazena o refresh_token CRIPTOGRAFADO. Usamos LargeBinary para bytes.
    encrypted_refresh_token: bytes = Column(
        LargeBinary,
        nullable=False,
        doc="The encrypted OAuth2 refresh token provided by Google.",
    )

    # Armazena a lista de escopos que foram concedidos com este token.
    scopes: list = Column(
        JSON,
        nullable=False,
        doc="A list of OAuth scopes granted by the user for this token.",
    )

    # Relacionamento de volta para o User.
    # Assumimos que o modelo User terá um relacionamento 'google_oauth_token'.
    user: Mapped["User"] = relationship(
        "User",
        back_populates="google_oauth_token",
        uselist=False,  # É uma relação um-para-um
    )

    def __repr__(self):
        return f"<GoogleOAuthToken(id={self.id}, user_id='{self.user_id}')>"
