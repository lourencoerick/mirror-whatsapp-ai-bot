# app/services/debounce/message_debounce.py

import asyncio
import json
import uuid as uuid_pkg
from typing import (
    Dict,
    Any,
    Callable,
    Coroutine,
    Optional,
    List,
)
from loguru import logger
import redis.asyncio as aioredis  # Para type hinting

DEFAULT_DEBOUNCE_DELAY_SECONDS = 8.0
REDIS_KEY_PREFIX = "debounce:convo"
REDIS_KEY_TTL_SECONDS = int(DEFAULT_DEBOUNCE_DELAY_SECONDS * 3 + 300)


class MessageDebounceService:
    """
    Manages debounce logic for incoming messages using a provided Redis client.
    Timers are local to each instance of this service (ideally one per ARQ worker process).
    Validates against a shared debounce token in Redis before processing.
    Accumulates message contents.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        default_delay_seconds: float = DEFAULT_DEBOUNCE_DELAY_SECONDS,
    ):
        """
        Initializes the MessageDebounceService.

        Args:
            redis_client: An initialized redis.asyncio.Redis client instance.
            default_delay_seconds: Default delay for debouncing.
        """
        if not isinstance(redis_client, aioredis.Redis):
            raise TypeError("redis_client must be an instance of redis.asyncio.Redis")

        self._debounce_timers: Dict[str, asyncio.TimerHandle] = {}
        self._processing_locks: Dict[str, asyncio.Lock] = (
            {}
        )  # Locks locais por conversation_id
        self._default_delay_seconds = default_delay_seconds
        self._redis_client_instance = redis_client  # Armazena o cliente Redis fornecido

        logger.info(
            f"MessageDebounceService instance initialized with {default_delay_seconds}s delay, using provided Redis client."
        )

    async def _get_redis_client(self) -> aioredis.Redis:
        """Returns the configured Redis client instance."""
        if not self._redis_client_instance:
            logger.critical(
                "CRITICAL_ERROR: _redis_client_instance is None in _get_redis_client. This should not happen."
            )
            raise RuntimeError(
                "Internal Error: Redis client not available in DebounceService instance."
            )
        return self._redis_client_instance

    def _generate_redis_key(self, conversation_id_str: str) -> str:
        """Generates the Redis key for storing debounce data."""
        return f"{REDIS_KEY_PREFIX}:{conversation_id_str}:data"

    async def _get_local_lock(self, conversation_id_str: str) -> asyncio.Lock:
        """
        Gets or creates a local asyncio.Lock for a given conversation ID.
        This lock is per instance of MessageDebounceService (i.e., per ARQ worker process).
        """
        if conversation_id_str not in self._processing_locks:
            self._processing_locks[conversation_id_str] = asyncio.Lock()
        return self._processing_locks[conversation_id_str]

    async def _trigger_processing_callback(
        self,
        conversation_id_str: str,
        expected_debounce_token: str,
        task_enqueuer_func: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ):
        """
        Internal callback executed by asyncio.call_later when a debounce timer expires.
        Validates the debounce token against Redis and, if valid, calls the task_enqueuer_func.
        """
        local_lock = await self._get_local_lock(conversation_id_str)
        async with local_lock:
            self._debounce_timers.pop(conversation_id_str, None)
            logger.debug(
                f"Debounce timer callback triggered for conv_id={conversation_id_str} with expected_token={expected_debounce_token}."
            )

            redis_cli = await self._get_redis_client()
            redis_key = self._generate_redis_key(conversation_id_str)

            try:
                lua_script = """
                local key = KEYS[1]
                local expected_token = ARGV[1]
                local data_flat = redis.call('HGETALL', key)
                if #data_flat == 0 then return nil end
                local stored_token
                for i=1,#data_flat,2 do
                    if data_flat[i] == 'debounce_token' then
                        stored_token = data_flat[i+1]
                        break
                    end
                end
                if stored_token == expected_token then
                    redis.call('DEL', key)
                    return data_flat
                else
                    return nil
                end
                """
                num_keys = 1
                raw_result_data_list: Optional[List[bytes]] = await redis_cli.eval(
                    lua_script,
                    num_keys,
                    redis_key,
                    expected_debounce_token,
                )

                if not raw_result_data_list:
                    logger.info(
                        f"Debounce trigger for conv_id={conversation_id_str}: Token mismatch, key expired/deleted, or no data. "
                        f"Expected token '{expected_debounce_token}'. Obsolete callback. Skipping."
                    )
                    return

                stored_data_dict: Dict[str, str] = {}
                for i in range(0, len(raw_result_data_list), 2):
                    stored_data_dict[raw_result_data_list[i].decode("utf-8")] = (
                        raw_result_data_list[i + 1].decode("utf-8")
                    )

                logger.info(
                    f"Debounce trigger for conv_id={conversation_id_str}: Token match. Data retrieved and key deleted from Redis."
                )
                logger.trace(
                    f"Retrieved data from Redis for {conversation_id_str}: {stored_data_dict}"
                )

                message_contents_json = stored_data_dict.get("message_contents", "[]")
                message_contents: List[str] = json.loads(message_contents_json)
                merged_content = " ".join(message_contents).strip()

                # Reconstruir o base_payload_for_task a partir do stored_data_dict
                # Os IDs já estão como strings no Redis, converter para UUID se necessário
                final_payload_for_task = {
                    "account_id": uuid_pkg.UUID(stored_data_dict["account_id"]),
                    "conversation_id": uuid_pkg.UUID(
                        stored_data_dict["conversation_id"]
                    ),
                    "merged_content": merged_content,
                    # Adicionar outros campos do base_payload_for_task se foram armazenados
                }

                # Adicionar quaisquer outros campos que foram armazenados em stored_data_dict
                # e que são esperados por task_enqueuer_func, além dos IDs e merged_content.
                # Ex: Se você armazenou "last_user_message_id" no Redis:
                # if "last_user_message_id" in stored_data_dict:
                #    final_payload_for_task["last_user_message_id"] = stored_data_dict["last_user_message_id"]

                asyncio.create_task(task_enqueuer_func(final_payload_for_task))
                logger.debug(
                    f"Created background task via task_enqueuer_func for conv_id={conversation_id_str} "
                    f"with {len(message_contents)} merged message(s)."
                )

            except aioredis.RedisError as re:
                logger.exception(
                    f"Redis error in _trigger_processing_callback for conv_id={conversation_id_str}: {re}"
                )
            except json.JSONDecodeError as je:
                logger.error(
                    f"JSON decode error processing Redis data for conv_id={conversation_id_str}: {je}. Data: {stored_data_dict if 'stored_data_dict' in locals() else 'N/A'}"
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error in _trigger_processing_callback for conv_id={conversation_id_str}: {e}"
                )

    async def handle_incoming_message(
        self,
        conversation_id: uuid_pkg.UUID,
        current_message_content: str,
        base_payload_for_task: Dict[
            str, Any
        ],  # Deve conter account_id (UUID), conversation_id (UUID)
        # e quaisquer outros dados que a task_enqueuer_func precise
        # que não sejam o merged_content.
        task_enqueuer_func: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
        debounce_seconds: Optional[float] = None,
    ):
        conversation_id_str = str(conversation_id)
        delay = (
            debounce_seconds
            if debounce_seconds is not None
            else self._default_delay_seconds
        )

        if not current_message_content or not current_message_content.strip():
            logger.debug(
                f"Empty message content received for conv_id={conversation_id_str}. Skipping debounce handling."
            )
            return

        current_debounce_token = str(uuid_pkg.uuid4())
        redis_cli = await self._get_redis_client()
        redis_key = self._generate_redis_key(conversation_id_str)

        local_lock = await self._get_local_lock(conversation_id_str)
        async with local_lock:
            try:
                async with redis_cli.pipeline(transaction=True) as pipe:
                    await pipe.watch(redis_key)
                    existing_data_raw = await redis_cli.hgetall(
                        redis_key
                    )  # Executado fora do MULTI mas com WATCH

                    pipe.multi()  # Iniciar transação

                    existing_data = (
                        {
                            k.decode("utf-8"): v.decode("utf-8")
                            for k, v in existing_data_raw.items()
                        }
                        if existing_data_raw
                        else {}
                    )

                    message_contents: List[str]
                    if existing_data and "message_contents" in existing_data:
                        try:
                            message_contents = json.loads(
                                existing_data["message_contents"]
                            )
                            if not isinstance(message_contents, list):
                                message_contents = []  # Sanity check
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Corrupted message_contents in Redis for {conversation_id_str}. Starting new list."
                            )
                            message_contents = []
                        message_contents.append(current_message_content)
                        logger.debug(
                            f"Appending to existing debounce data for {conversation_id_str}. Total parts: {len(message_contents)}"
                        )
                    else:
                        message_contents = [current_message_content]
                        logger.debug(
                            f"Initializing new debounce data for {conversation_id_str}."
                        )

                    # Preparar dados para armazenar. Incluir todos os campos de base_payload_for_task.
                    # Garantir que os UUIDs sejam convertidos para string para armazenamento no Redis.
                    payload_to_store: Dict[str, str] = {
                        "message_contents": json.dumps(message_contents),
                        "debounce_token": current_debounce_token,
                        "scheduled_at": str(asyncio.get_running_loop().time()),
                    }
                    # Adicionar/sobrescrever chaves do base_payload_for_task
                    for key, value in base_payload_for_task.items():
                        payload_to_store[key] = str(
                            value
                        )  # Converter tudo para string para Redis Hashes

                    pipe.hmset(redis_key, payload_to_store)
                    pipe.expire(redis_key, REDIS_KEY_TTL_SECONDS)

                    await pipe.execute()

                existing_local_timer = self._debounce_timers.pop(
                    conversation_id_str, None
                )
                if existing_local_timer:
                    existing_local_timer.cancel()
                    logger.debug(
                        f"Cancelled existing local timer for {conversation_id_str}."
                    )

                loop = asyncio.get_running_loop()
                new_local_timer = loop.call_later(
                    delay,
                    lambda: asyncio.create_task(
                        self._trigger_processing_callback(
                            conversation_id_str,
                            current_debounce_token,
                            task_enqueuer_func,
                        )
                    ),
                )
                self._debounce_timers[conversation_id_str] = new_local_timer
                logger.info(
                    f"Scheduled/Re-scheduled AI processing for conv_id={conversation_id_str} in {delay}s "
                    f"with debounce token {current_debounce_token}."
                )

            except aioredis.WatchError:
                logger.warning(
                    f"WatchError for {conversation_id_str} during handle_incoming_message. Retrying operation once."
                )
                # Simples retentativa pode ser útil aqui, pois a condição de corrida pode ser transitória.
                # Para uma lógica de retentativa mais robusta, seria necessário um loop.
                # Por ora, vamos apenas logar e a mensagem atual pode ser perdida para este ciclo de debounce.
                # Ou, você pode optar por não fazer nada e deixar o próximo evento de mensagem reiniciar o debounce.
            except aioredis.RedisError as re:
                logger.exception(
                    f"Redis error in handle_incoming_message for {conversation_id_str}: {re}"
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error in handle_incoming_message for {conversation_id_str}: {e}"
                )
