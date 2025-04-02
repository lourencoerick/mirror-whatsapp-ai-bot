import httpx
from typing import Dict, Any, List, Optional
from loguru import logger
from app.config import get_settings, Settings

settings: Settings = get_settings()

async_client = httpx.AsyncClient(timeout=30.0)


async def create_logical_evolution_instance(
    instance_name: str,
    logical_token: str,
    webhook_url: str,
) -> Dict[str, Any]:
    """
    Creates a logical Evolution API instance on a shared server.
    """
    shared_url = settings.EVOLUTION_API_SHARED_URL
    backend_key = settings.EVOLUTION_BACKEND_API_KEY

    headers = {"apikey": backend_key, "Content-Type": "application/json"}

    payload = {
        "instanceName": instance_name,
        "token": logical_token,
        "qrcode": False,
        "integration": "WHATSAPP-BAILEYS",
        "webhook": {
            "url": webhook_url,
            "events": ["QRCODE_UPDATED", "MESSAGES_UPSERT", "CONNECTION_UPDATE"],
            "webhookByEvents": True,
            "webhookBase64": True,
            "enabled": True,
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{shared_url}/instance/create", json=payload, headers=headers
            )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        logger.exception(f"HTTP error creating instance: {e.response.text}")
        raise
    except Exception as e:
        logger.exception("Error creating instance")
        raise


async def generate_connection_qrcode(
    shared_url: str, instance_name: str, api_key: str
) -> Dict[str, Any]:
    backend_key = settings.EVOLUTION_BACKEND_API_KEY

    headers = {
        "apikey": api_key,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{shared_url}/instance/connect/{instance_name}", headers=headers
            )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        logger.exception(f"HTTP error getting instance: {e.response.text}")
        raise
    except Exception as e:
        logger.exception(f"Error getting instance: {e}")
        raise


async def set_evolution_instance_webhooks(
    instance_name: str,
    shared_url: str,
    api_key: str,
    webhook_url: str,
    webhook_events: Optional[List[str]] = None,
) -> Dict[str, Any]:

    headers = {"apikey": api_key, "Content-Type": "application/json"}

    payload = {
        "enabled": True,
        "url": webhook_url,
        "events": (
            ["QRCODE_UPDATED", "MESSAGES_UPSERT", "CONNECTION_UPDATE"]
            if webhook_events is None
            else webhook_events
        ),
        "webhookByEvents": True,
        "webhookBase64": True,
        "enabled": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{shared_url}/webhook/set/{instance_name}",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        logger.exception(f"HTTP error creating instance: {e.response.text}")
        raise
    except Exception as e:
        logger.exception("Error creating instance")
        raise
