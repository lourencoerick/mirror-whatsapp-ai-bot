# app/api/schemas/internal_messaging.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class InternalIncomingMessageDTO(BaseModel):
    """
    DTO padronizado representando uma mensagem de entrada após a transformação,
    pronta para ser processada pela lógica de negócios principal.
    """

    # Identificadores da nossa plataforma (preenchidos pela função de transformação)
    account_id: UUID
    inbox_id: UUID
    contact_id: UUID
    conversation_id: UUID

    # Dados da mensagem original
    external_message_id: str = Field(
        ...,
        description="ID da mensagem na plataforma de origem (ex: WAMID, ID da Evolution).",
    )
    sender_identifier: str = Field(
        ...,
        description="Identificador do remetente na plataforma de origem (ex: número de telefone, remoteJid).",
    )

    message_content: Optional[str] = Field(
        None, description="Conteúdo principal da mensagem (texto, caption de mídia)."
    )

    internal_content_type: str = Field(
        ...,
        description="Tipo da mensagem normalizado para o sistema interno (ex: text, image, audio).",
    )

    message_timestamp: datetime = Field(
        ..., description="Timestamp da mensagem original (UTC)."
    )

    # Atributos brutos ou específicos da plataforma que podem ser úteis para processamento posterior
    # ou para armazenar metadados completos.
    # Ex: ID de mídia para download, contexto de resposta, botões clicados, etc.
    raw_message_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Atributos brutos ou específicos da plataforma da mensagem original.",
    )

    source_api: Literal["whatsapp_cloud", "whatsapp_evolution"] = Field(
        ..., description="API de origem da mensagem, para referência."
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "account_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "inbox_id": "b1c2d3e4-f5g6-7890-1234-567890abcdef",
                "contact_id": "c1d2e3f4-g5h6-7890-1234-567890abcdef",
                "conversation_id": "d1e2f3g4-h5i6-7890-1234-567890abcdef",
                "external_message_id": "wamid.XYZ",
                "sender_identifier": "16505551234",
                "message_content": "Olá, gostaria de mais informações.",
                "internal_message_type": "text",
                "message_timestamp": "2023-10-27T10:30:00Z",
                "raw_message_attributes": {
                    "whatsapp_context": {"from": "16505550000", "id": "wamid.PREVIOUS"}
                },
                "source_api": "whatsapp_cloud",
            }
        }
