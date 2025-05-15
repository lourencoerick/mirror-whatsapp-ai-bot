# app/api/schemas/queue_payload.py

from pydantic import BaseModel, Field
from typing import Dict, Any, Literal, Optional


class IncomingMessagePayload(BaseModel):
    """
    Payload queued for the ARQ task to process an incoming message.
    Contains raw data from the source platform.
    """

    source_api: Literal["whatsapp_cloud", "whatsapp_evolution", "simulation"] = Field(
        ..., description="Identifies the API source of the message."
    )

    # Identifier of your business entity in the source platform.
    # For WhatsApp Cloud: the phone_number_id of your business that received the message.
    # For Evolution API: the instance_name of your Evolution instance.
    business_identifier: str = Field(
        ..., description="Identifier of your account/inbox on the source platform."
    )

    # Raw message data from the external platform.
    # This dictionary will be parsed into a platform-specific schema (e.g., WhatsAppMessageSchema)
    # inside the transformation function of the ARQ task.
    external_raw_message: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw payload of the individual message from the source platform.",
    )

    internal_dto_partial_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data for InternalIncomingMessageDTO used in simulation environment",
    )

    class Config:
        json_schema_extra = {
            "example_whatsapp_cloud": {
                "source_api": "whatsapp_cloud",
                "business_identifier": "16505551234",
                "external_raw_message": {
                    "from": "16505555678",
                    "id": "wamid.HBgLMTY1MDM3NzcxNzAVaQwTextBILVFFQkZFNzIzQjRDNzQ1NkQ5RAA=",
                    "timestamp": "1660607046",
                    "text": {"body": "Hello world"},
                    "type": "text",
                    "contacts": [
                        {"profile": {"name": "Customer Name"}, "wa_id": "16505555678"}
                    ],
                },
            },
            "example_evolution_api": {
                "source_api": "whatsapp_evolution",
                "business_identifier": "my_evolution_instance_name",
                "external_raw_message": {
                    "key": {
                        "remoteJid": "16505555678@c.us",
                        "fromMe": False,
                        "id": "ABCDEF123456",
                    },
                    "message": {"conversation": "Hello from Evolution!"},
                    "messageType": "conversation",
                    "pushName": "Evolution Contact Name",
                },
            },
        }
