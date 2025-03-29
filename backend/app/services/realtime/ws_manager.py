from uuid import UUID
from typing import Dict, List, Union
from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    """
    Central manager for WebSocket connections.

    Manages connections organized by conversation_id or account_id.
    Allows message broadcast and removes disconnected connections.
    """

    def __init__(self):
        self.active_connections: Dict[Union[UUID, str], List[WebSocket]] = {}

    async def connect(self, identifier: Union[UUID, str], websocket: WebSocket):
        if identifier not in self.active_connections:
            self.active_connections[identifier] = []
        self.active_connections[identifier].append(websocket)
        logger.info(
            f"[ws] Client connected to {identifier} "
            f"({len(self.active_connections[identifier])} total)"
        )
        logger.debug(
            f"[ws] Current identifiers: {list(self.active_connections.keys())}"
        )

    def disconnect(self, identifier: Union[UUID, str], websocket: WebSocket):
        connections = self.active_connections.get(identifier)
        if not connections:
            return

        if websocket in connections:
            connections.remove(websocket)
            logger.info(
                f"[ws] Client disconnected from {identifier} "
                f"({len(connections)} remaining)"
            )

        if not connections:
            del self.active_connections[identifier]
            logger.debug(f"[ws] No more clients in {identifier}, cleaned up.")

    async def broadcast(self, identifier: Union[UUID, str], message: dict):
        connections = self.active_connections.get(identifier, [])
        if not connections:
            logger.debug(f"[ws] No clients to broadcast in {identifier}")
            return

        logger.debug(
            f"[ws] Broadcasting to {len(connections)} client(s) in {identifier}"
        )
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    f"[ws] Failed to send message to client in {identifier}: {e}"
                )


manager_instance = WebSocketManager()
