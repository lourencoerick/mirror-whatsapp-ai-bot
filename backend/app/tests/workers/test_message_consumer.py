import json
import pytest
from unittest.mock import patch, MagicMock
from app.workers.message_consumer import MessageConsumer
from app.services.queue.redis_queue import RedisQueue


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_redis_queue():
    return MagicMock(spec=RedisQueue)


@pytest.fixture
def mock_log_message():
    with patch("app.workers.message_consumer.log_message") as mocked:
        yield mocked


@pytest.fixture
def valid_message():
    return {
        "content": "Oi",
        "direction": "in",
        "account_id": 1,
        "inbox_id": 1,
        "conversation_id": 1,
        "contact_id": 1,
    }


def test_handle_valid_message(
    mock_db, mock_log_message, mock_redis_queue, valid_message
):
    mock_log_message.return_value = MagicMock(id=123)

    consumer = MessageConsumer(redis_queue=mock_redis_queue)
    consumer._handle_message(db=mock_db, data=valid_message)

    mock_log_message.assert_called_once()


def test_handle_message_with_invalid_schema_logs_warning(mock_db, mock_redis_queue):
    invalid_data = {"foo": "bar"}  # missing required fields
    consumer = MessageConsumer(redis_queue=mock_redis_queue)

    with patch("app.workers.message_consumer.logger.warning") as mock_log:
        consumer._handle_message(db=mock_db, data=invalid_data)
        mock_log.assert_called_once()
        assert "Invalid message payload" in mock_log.call_args[0][0]


def test_run_skips_invalid_json(mock_redis_queue):
    mock_redis_queue.dequeue = MagicMock(
        side_effect=["{invalid_json", KeyboardInterrupt]
    )
    consumer = MessageConsumer(redis_queue=mock_redis_queue)

    with patch("app.workers.message_consumer.logger.warning") as mock_log:
        with patch("app.workers.message_consumer.get_db") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = MagicMock()
            try:
                consumer.run()  # Vai rodar 1x, depois lançar KeyboardInterrupt
            except KeyboardInterrupt:
                pass

    assert any("malformed JSON" in str(c[0]) for c in mock_log.call_args_list)


def test_handle_message_log_failure(
    mock_db, mock_log_message, mock_redis_queue, valid_message
):
    mock_log_message.return_value = None
    consumer = MessageConsumer(redis_queue=mock_redis_queue)

    with patch("app.workers.message_consumer.logger.warning") as mock_log:
        consumer._handle_message(db=mock_db, data=valid_message)
        mock_log.assert_called_with("[consumer] Failed to save message")
