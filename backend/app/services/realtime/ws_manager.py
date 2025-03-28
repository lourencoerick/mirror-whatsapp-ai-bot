from uuid import UUID
from typing import Dict, List
from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    """
    Central manager for WebSocket connections, organizado por `conversation_id`.

    Manages connections, allows message broadcast and romove disconnected connections.
    """

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, conversation_id: int, websocket: WebSocket):
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
        logger.info(
            f"[ws] Client connected to conversation {conversation_id} "
            f"({len(self.active_connections[conversation_id])} total)"
        )
        logger.debug(
            f"[ws] Current conversations: {list(self.active_connections.keys())}"
        )

    def disconnect(self, conversation_id: UUID, websocket: WebSocket):
        """
        Remove uma conexão WebSocket da conversa informada.
        """
        connections = self.active_connections.get(conversation_id)
        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)
            logger.info(
                f"[ws] Client disconnected from conversation {conversation_id} "
                f"({len(connections)} remaining)"
            )

        if not connections:
            del self.active_connections[conversation_id]
            logger.debug(
                f"[ws] No more clients in conversation {conversation_id}, cleaned up."
            )

    async def broadcast(self, conversation_id: UUID, message: dict):
        connections = self.active_connections.get(conversation_id, [])
        if not connections:
            logger.debug(
                f"[ws] No clients to broadcast in conversation {conversation_id}"
            )
            return

        logger.debug(
            f"[ws] Broadcasting to {len(connections)} client(s) in conversation {conversation_id}"
        )
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    f"[ws] Failed to send message to client in conversation {conversation_id}: {e}"
                )


manager_instance = WebSocketManager()
