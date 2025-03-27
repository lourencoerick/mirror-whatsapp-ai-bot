from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import Dict, List
from app.services.realtime.ws_manager import manager_instance


router = APIRouter()

# Active WebSocket connections organized by account_id
active_connections: Dict[int, List[WebSocket]] = {}


@router.websocket("/ws/conversations/{conversation_id}")
async def websocket_conversation_endpoint(websocket: WebSocket, conversation_id: int):
    """
    WebSocket endpoint to subscribe to real-time updates for a specific conversation.

    - Accepts client connection
    - Registers it with WebSocketManager
    - Keeps connection open to receive future messages
    - Removes client from manager on disconnect
    """
    await websocket.accept()
    logger.info(f"[ws] WebSocket accepted for conversation {conversation_id}")

    await manager_instance.connect(conversation_id, websocket)

    try:
        while True:
            await websocket.receive_text()  # Optional: receive pings or presence
    except WebSocketDisconnect:
        manager_instance.disconnect(conversation_id, websocket)
        logger.info(f"[ws] WebSocket disconnected from conversation {conversation_id}")
