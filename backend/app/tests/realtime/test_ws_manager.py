import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket
from app.services.realtime.ws_manager import WebSocketManager


# Fixture to create a new instance of WebSocketManager for each test.
@pytest.fixture
def manager():
    return WebSocketManager()


# Fixture to create a fake WebSocket with an asynchronous send_json method.
@pytest.fixture
def fake_websocket():
    ws = MagicMock(spec=WebSocket)
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_adds_websocket(manager, fake_websocket):
    conversation_id = 1
    # Before connecting, the conversation should not exist.
    assert conversation_id not in manager.active_connections

    # Connect the WebSocket.
    await manager.connect(conversation_id, fake_websocket)

    # Verify that the WebSocket was added correctly.
    assert conversation_id in manager.active_connections
    assert fake_websocket in manager.active_connections[conversation_id]


@pytest.mark.asyncio
async def test_connect_multiple_websockets(manager):
    conversation_id = 2
    # Create two fake WebSockets.
    fake_ws1 = MagicMock(spec=WebSocket)
    fake_ws1.send_json = AsyncMock()
    fake_ws2 = MagicMock(spec=WebSocket)
    fake_ws2.send_json = AsyncMock()

    # Connect both WebSockets to the same conversation.
    await manager.connect(conversation_id, fake_ws1)
    await manager.connect(conversation_id, fake_ws2)

    # Verify that both WebSockets have been added.
    assert len(manager.active_connections[conversation_id]) == 2


def test_disconnect_removes_websocket(manager):
    conversation_id = 3
    fake_ws = MagicMock(spec=WebSocket)

    # Manually add a connection to the conversation.
    manager.active_connections[conversation_id] = [fake_ws]

    # Remove the connection.
    manager.disconnect(conversation_id, fake_ws)

    # Since the list is empty, the conversation key should be removed.
    assert conversation_id not in manager.active_connections


def test_disconnect_removes_only_specified(manager):
    conversation_id = 4
    fake_ws1 = MagicMock(spec=WebSocket)
    fake_ws2 = MagicMock(spec=WebSocket)

    # Add two connections for the conversation.
    manager.active_connections[conversation_id] = [fake_ws1, fake_ws2]

    # Remove only one of the connections.
    manager.disconnect(conversation_id, fake_ws1)

    # The conversation should still exist with only the remaining connection.
    assert conversation_id in manager.active_connections
    assert fake_ws1 not in manager.active_connections[conversation_id]
    assert fake_ws2 in manager.active_connections[conversation_id]


def test_disconnect_nonexistent(manager):
    # Calling disconnect on a non-existent conversation should not raise an exception.
    fake_ws = MagicMock(spec=WebSocket)
    try:
        manager.disconnect(999, fake_ws)
    except Exception:
        pytest.fail("disconnect raised an unexpected exception!")


@pytest.mark.asyncio
async def test_broadcast_calls_send_json(manager, fake_websocket):
    conversation_id = 5
    message = {"text": "Hello"}

    # Connect a WebSocket to the conversation.
    await manager.connect(conversation_id, fake_websocket)

    # Call broadcast and verify that send_json was called with the correct message.
    await manager.broadcast(conversation_id, message)
    fake_websocket.send_json.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_broadcast_handles_no_connections(manager):
    # When there are no connections for the conversation, broadcast should not raise an exception.
    try:
        await manager.broadcast(999, {"text": "Hello"})
    except Exception:
        pytest.fail(
            "broadcast raised an unexpected exception when there were no connections!"
        )


@pytest.mark.asyncio
async def test_broadcast_handles_send_json_exception(manager):
    conversation_id = 6
    # Create a WebSocket that simulates an error when sending a message.
    fake_ws = MagicMock(spec=WebSocket)
    fake_ws.send_json = AsyncMock(side_effect=Exception("send error"))

    await manager.connect(conversation_id, fake_ws)

    # broadcast should catch the exception and not propagate it.
    try:
        await manager.broadcast(conversation_id, {"text": "Hello"})
    except Exception:
        pytest.fail("broadcast propagated an exception when send_json failed!")
