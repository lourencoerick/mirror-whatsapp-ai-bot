# app/api/schemas/external/whatsapp_cloud.py (novo arquivo ou local apropriado)
from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class MetaTextObject(BaseModel):
    preview_url: bool = False
    body: str


class MetaSendMessageBase(BaseModel):
    messaging_product: Literal["whatsapp"] = "whatsapp"
    recipient_type: Literal["individual"] = "individual"  # Geralmente individual
    to: str  # Recipient phone number (E.164 format)


class MetaSendTextMessagePayload(MetaSendMessageBase):
    type: Literal["text"] = "text"
    text: MetaTextObject
