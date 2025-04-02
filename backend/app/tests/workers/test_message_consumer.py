from datetime import datetime, timezone
from uuid import uuid4
import pytest
from unittest.mock import patch, MagicMock
from app.workers.message_consumer import MessageConsumer
from app.services.queue.redis_queue import RedisQueue


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_input_queue():
    return MagicMock(spec=RedisQueue)


@pytest.fixture
def mock_output_queue():
    return MagicMock(spec=RedisQueue)


@pytest.fixture
def mock_get_or_create_message():
    with patch("app.workers.message_consumer.get_or_create_message") as mocked:
        yield mocked


account_id = uuid4()
inbox_id = uuid4()
contact_id = uuid4()
conversation_id = uuid4()


@pytest.fixture
def valid_message():
    return {
        "content": "Oi",
        "direction": "in",
        "account_id": account_id,
        "inbox_id": inbox_id,
        "contact_id": contact_id,
        "conversation_id": conversation_id,
        "source_id": "msg-123",
        "message_timestamp": datetime.utcnow().isoformat(),
        "content_type": "text",
        "status": "received",
        "private": False,
        "content_attributes": {},
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_valid_message(
    mock_db,
    mock_get_or_create_message,
    mock_input_queue,
    mock_output_queue,
    valid_message,
):
    mock_get_or_create_message.return_value = MagicMock(id=123)

    consumer = MessageConsumer(
        input_queue_name="message_queue",
        output_queue_name="ready_for_processing_queue",
    )
    consumer.input_queue = mock_input_queue
    consumer.output_queue = mock_output_queue

    await consumer._handle_message(db=mock_db, data=valid_message)

    mock_get_or_create_message.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_skips_invalid_json(mock_input_queue, mock_output_queue):
    mock_input_queue.dequeue = MagicMock(
        side_effect=["{invalid_json", KeyboardInterrupt]
    )
    consumer = MessageConsumer()
    consumer.input_queue = mock_input_queue
    consumer.output_queue = mock_output_queue

    with patch("app.workers.message_consumer.logger.warning") as mock_log:
        try:
            await consumer.run()
        except KeyboardInterrupt:
            pass

    assert any("malformed JSON" in str(c[0]) for c in mock_log.call_args_list)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_message_with_invalid_schema_logs_warning(
    mock_db, mock_input_queue, mock_output_queue
):
    invalid_data = {"foo": "bar"}
    consumer = MessageConsumer()
    consumer.input_queue = mock_input_queue
    consumer.output_queue = mock_output_queue

    with patch("app.workers.message_consumer.logger.warning") as mock_log:
        await consumer._handle_message(db=mock_db, data=invalid_data)
        mock_log.assert_called_once()
        assert "Invalid message payload" in mock_log.call_args[0][0]


@pytest.fixture
def mock_conversation_find_by_id():
    with patch("app.workers.message_consumer.find_conversation_by_id") as mocked:
        yield mocked


@pytest.fixture
def mock_update_last_message_snapshot():
    with patch("app.workers.message_consumer.update_last_message_snapshot") as mocked:
        yield mocked


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_message_log_failure(
    mock_db,
    mock_get_or_create_message,
    mock_input_queue,
    mock_output_queue,
    valid_message,
):
    mock_get_or_create_message.return_value = None
    consumer = MessageConsumer()
    consumer.input_queue = mock_input_queue
    consumer.output_queue = mock_output_queue

    with patch("app.workers.message_consumer.logger.warning") as mock_log:
        await consumer._handle_message(db=mock_db, data=valid_message)
        mock_log.assert_called_with("[consumer] Failed to save message")
