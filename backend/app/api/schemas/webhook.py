from pydantic import BaseModel
from typing import Optional, Dict, Any


class EvolutionWebhookMessageKey(BaseModel):
    remoteJid: Optional[str] = None
    fromMe: Optional[bool] = None
    id: Optional[str] = None


class EvolutionWebhookMessageData(BaseModel):
    key: Optional[EvolutionWebhookMessageKey] = None
    message: Optional[Dict[str, Any]] = None
    messageType: Optional[str] = None
    messageTimestamp: Optional[int] = None
    instanceId: Optional[str] = None


class EvolutionWebhookPayload(BaseModel):
    event: Optional[str] = None
    data: Optional[EvolutionWebhookMessageData] = None
