# backend/app/services/message_debounce_service.py

import asyncio
import json
import uuid as uuid_pkg  # Para gerar tokens e para type hinting
from typing import (
    Dict,
    Any,
    Callable,
    Coroutine,
    Optional,
    List,
    Awaitable,
)  # Adicionado Awaitable
from loguru import logger
import redis.asyncio as aioredis  # Para type hinting


# from app.config import settings # Não precisamos de settings aqui diretamente

DEFAULT_DEBOUNCE_DELAY_SECONDS = 5.0  # 5 segundos parece um bom default
REDIS_KEY_PREFIX = "debounce:convo"
# TTL para a chave Redis um pouco maior que o delay para limpeza, em segundos
# Ajustado para ser mais generoso, caso o processamento do callback atrase um pouco.
REDIS_KEY_TTL_SECONDS = int(
    DEFAULT_DEBOUNCE_DELAY_SECONDS * 3 + 300
)  # Ex: 3x delay + 5 minutos

RedisClientGetter = Callable[[], Awaitable[Optional[aioredis.Redis]]]


class MessageDebounceService:
    """
    Manages debounce logic for incoming messages using Redis for shared state.
    Timers are local to each FastAPI instance, validating against a shared
    debounce token in Redis before processing. Accumulates message contents.
    """

    def __init__(
        self,
        default_delay_seconds: float = DEFAULT_DEBOUNCE_DELAY_SECONDS,
        redis_client_getter: Optional[RedisClientGetter] = None,
    ):  # Adicionado getter
        self._debounce_timers: Dict[str, asyncio.TimerHandle] = {}
        self._processing_locks: Dict[str, asyncio.Lock] = {}
        self._default_delay_seconds = default_delay_seconds

        self._redis_client_getter = redis_client_getter  # Armazena o getter
        self._redis_client_instance: Optional[aioredis.Redis] = (
            None  # Cache para o cliente obtido
        )

        if redis_client_getter:
            logger.info(
                f"MessageDebounceService initialized with {default_delay_seconds}s delay (Redis backend, via getter)."
            )
        else:
            logger.warning(
                f"MessageDebounceService initialized with {default_delay_seconds}s delay, "
                "BUT NO Redis client getter provided. _get_redis_client will fail until getter is set."
            )

    async def _get_redis_client(self) -> aioredis.Redis:
        if self._redis_client_instance is None:
            if self._redis_client_getter:
                self._redis_client_instance = await self._redis_client_getter()
                if self._redis_client_instance is None:
                    logger.error(
                        "Redis client getter returned None for DebounceService."
                    )
                    raise RuntimeError("Redis client getter returned None.")
                logger.debug(
                    "Dedicated Redis client obtained via getter for DebounceService."
                )
            else:
                logger.error(
                    "No Redis client getter configured for MessageDebounceService. "
                    "Ensure service is initialized correctly with a getter function."
                )
                raise RuntimeError(
                    "Redis client getter not configured for DebounceService."
                )
        return self._redis_client_instance

    async def _get_local_lock(self, conversation_id_str: str) -> asyncio.Lock:
        """Manages local asyncio locks for operations on the same conversation_id within a single process."""
        if conversation_id_str not in self._processing_locks:
            self._processing_locks[conversation_id_str] = asyncio.Lock()
        return self._processing_locks[conversation_id_str]

    def _generate_redis_key(self, conversation_id_str: str) -> str:
        """Generates the Redis key for storing debounce data."""
        return f"{REDIS_KEY_PREFIX}:{conversation_id_str}:data"

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
        # Usar lock local para evitar race conditions na mesma instância FastAPI
        # se múltiplos callbacks para a mesma conversa fossem agendados (improvável com a lógica atual, mas seguro)
        local_lock = await self._get_local_lock(conversation_id_str)
        async with local_lock:
            # Limpar o timer local, pois ele já disparou.
            self._debounce_timers.pop(conversation_id_str, None)
            logger.debug(
                f"Debounce timer callback triggered for {conversation_id_str} with token {expected_debounce_token}."
            )

            redis_cli = await self._get_redis_client()
            redis_key = self._generate_redis_key(conversation_id_str)

            try:
                # Operação Atômica: Ler e Deletar se o token corresponder
                # Usaremos um script Lua para garantir atomicidade para "get-and-delete-if-match"
                # Alternativamente, poderíamos usar WATCH/MULTI/EXEC, mas Lua é mais direto para este caso.

                # Script Lua:
                # KEYS[1] - a chave do hash (redis_key)
                # ARGV[1] - o token esperado (expected_debounce_token)
                # Retorna os dados do hash se o token corresponder e deleta a chave, senão retorna nil.
                lua_script = """
                local key = KEYS[1]
                local expected_token = ARGV[1]
                local data = redis.call('HGETALL', key)
                if #data == 0 then
                    return nil -- Chave não existe
                end
                local stored_token
                for i=1,#data,2 do
                    if data[i] == 'debounce_token' then
                        stored_token = data[i+1]
                        break
                    end
                end
                if stored_token == expected_token then
                    redis.call('DEL', key)
                    return data -- Retorna todos os campos e valores como uma lista plana
                else
                    return nil -- Token não correspondeu
                end
                """

                # Registrar o script se ainda não foi feito (redis.asyncio pode não ter register_script como redis-py síncrono)
                # Vamos executar diretamente.
                # A resposta será uma lista plana [field1, value1, field2, value2, ...] ou None
                num_keys = 1
                raw_result_data_list = await redis_cli.eval(
                    lua_script,
                    num_keys,
                    redis_key,  # Argumento para KEYS[1]
                    expected_debounce_token,  # Argumento para ARGV[1]
                )

                if not raw_result_data_list:
                    logger.info(
                        f"Debounce trigger for {conversation_id_str}: Token mismatch or key expired/deleted in Redis. "
                        f"Expected '{expected_debounce_token}'. Obsolete callback. Skipping."
                    )
                    return

                # Converter a lista plana de volta para um dicionário
                stored_data = {}
                for i in range(0, len(raw_result_data_list), 2):
                    stored_data[raw_result_data_list[i].decode("utf-8")] = (
                        raw_result_data_list[i + 1].decode("utf-8")
                    )

                logger.info(
                    f"Debounce trigger for {conversation_id_str}: Token match. Data retrieved and key deleted from Redis."
                )

                # Desserializar e preparar payload para o enfileirador de tarefas
                message_contents_json = stored_data.get("message_contents", "[]")
                message_contents = json.loads(message_contents_json)
                merged_content = " ".join(message_contents)

                final_payload_for_task = {
                    "account_id": uuid_pkg.UUID(stored_data["account_id"]),
                    "conversation_id": uuid_pkg.UUID(stored_data["conversation_id"]),
                    "merged_content": merged_content,
                    # Não precisamos mais de initial_whatsapp_message_id ou all_whatsapp_message_ids
                    # se o ai_replier não os usa e o MessageConsumer já salvou os fragmentos.
                }

                # Enfileirar a tarefa de processamento da IA
                asyncio.create_task(task_enqueuer_func(final_payload_for_task))
                logger.debug(
                    f"Created background task via task_enqueuer_func for {conversation_id_str} "
                    f"with merged content: '{merged_content[:100]}...'"
                )

            except aioredis.RedisError as re:
                logger.exception(
                    f"Redis error in _trigger_processing_callback for {conversation_id_str}: {re}"
                )
            except json.JSONDecodeError as je:
                logger.error(
                    f"JSON decode error processing Redis data for {conversation_id_str}: {je}. Data: {stored_data if 'stored_data' in locals() else 'N/A'}"
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error in _trigger_processing_callback for {conversation_id_str}: {e}"
                )

    async def handle_incoming_message(
        self,
        conversation_id: uuid_pkg.UUID,
        current_message_content: str,
        # Não precisamos mais de current_trigger_message_id (do DB) nem current_whatsapp_message_id aqui
        base_payload_for_task: Dict[
            str, Any
        ],  # Deve conter account_id (UUID), conversation_id (UUID)
        task_enqueuer_func: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
        debounce_seconds: Optional[float] = None,
    ):
        """
        Handles an incoming message fragment. Accumulates content in Redis and
        schedules/re-schedules a debounced call to task_enqueuer_func.
        """
        conversation_id_str = str(conversation_id)
        delay = (
            debounce_seconds
            if debounce_seconds is not None
            else self._default_delay_seconds
        )

        current_debounce_token = str(
            uuid_pkg.uuid4()
        )  # Novo token para esta (re)agenda
        redis_cli = await self._get_redis_client()
        redis_key = self._generate_redis_key(conversation_id_str)

        # Lock local para serializar acesso ao timer e à lógica de escrita no Redis para esta conversa
        local_lock = await self._get_local_lock(conversation_id_str)
        async with local_lock:
            try:
                # Usar transação Redis para garantir atomicidade na atualização dos dados de debounce
                async with redis_cli.pipeline(transaction=True) as pipe:
                    await pipe.watch(
                        redis_key
                    )  # Observar a chave para modificações concorrentes

                    # Ler dados existentes (fora da transação de escrita, mas a chave está observada)
                    existing_data_raw = await redis_cli.hgetall(redis_key)
                    existing_data = (
                        {
                            k.decode("utf-8"): v.decode("utf-8")
                            for k, v in existing_data_raw.items()
                        }
                        if existing_data_raw
                        else {}
                    )

                    pipe.multi()  # Iniciar bloco da transação

                    if existing_data and existing_data.get(
                        "debounce_token"
                    ):  # Anexar à sequência existente
                        message_contents = json.loads(
                            existing_data.get("message_contents", "[]")
                        )
                        message_contents.append(current_message_content)

                        payload_to_store = {
                            "account_id": existing_data[
                                "account_id"
                            ],  # Mantém o original
                            "conversation_id": existing_data[
                                "conversation_id"
                            ],  # Mantém o original
                            "message_contents": json.dumps(message_contents),
                            "debounce_token": current_debounce_token,  # Atualiza o token
                            "scheduled_at": str(
                                asyncio.get_running_loop().time()
                            ),  # Atualiza timestamp
                        }
                        logger.debug(
                            f"Appending to existing debounce data for {conversation_id_str}. Total parts: {len(message_contents)}"
                        )
                    else:  # Nova sequência de debounce
                        payload_to_store = {
                            "account_id": str(base_payload_for_task["account_id"]),
                            "conversation_id": str(
                                base_payload_for_task["conversation_id"]
                            ),
                            "message_contents": json.dumps([current_message_content]),
                            "debounce_token": current_debounce_token,
                            "scheduled_at": str(asyncio.get_running_loop().time()),
                        }
                        logger.debug(
                            f"Initializing new debounce data for {conversation_id_str}."
                        )

                    pipe.hmset(redis_key, payload_to_store)
                    pipe.expire(redis_key, REDIS_KEY_TTL_SECONDS)

                    await pipe.execute()  # Tenta executar a transação (HMSET, EXPIRE)

                # Se a transação Redis foi bem-sucedida, cancela timer local antigo e agenda novo
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
                    # lambda para garantir que create_task seja chamado no contexto correto do loop
                    # e para passar os argumentos corretos para o callback.
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
                    f"Scheduled/Re-scheduled AI processing for conversation {conversation_id_str} in {delay}s "
                    f"with debounce token {current_debounce_token}."
                )

            except aioredis.WatchError:
                # A chave foi modificada por outro processo/thread entre WATCH e EXEC.
                # Isso é raro com o lock local, mas possível se múltiplas instâncias FastAPI
                # acessarem quase simultaneamente.
                logger.warning(
                    f"WatchError for {conversation_id_str} during handle_incoming_message. "
                    "Key was modified concurrently. This message might be included in the next debounce cycle "
                    "triggered by the other modification, or a new cycle will start if this was the last message."
                )
                # Não re-tentamos automaticamente para manter a simplicidade. A lógica é que
                # o estado no Redis é a fonte da verdade, e o timer local é apenas um gatilho.
                # Se o token não bater, o callback não faz nada.
            except aioredis.RedisError as re:
                logger.exception(
                    f"Redis error in handle_incoming_message for {conversation_id_str}: {re}"
                )
                # Considerar o que fazer aqui. Re-levantar? Tentar um fallback?
            except Exception as e:
                logger.exception(
                    f"Unexpected error in handle_incoming_message for {conversation_id_str}: {e}"
                )


# --- Gerenciamento da Instância Global ---
_global_message_debounce_service: Optional[MessageDebounceService] = None


def init_message_debounce_service(
    default_delay_seconds: float = DEFAULT_DEBOUNCE_DELAY_SECONDS,
    redis_client_getter: Optional[
        RedisClientGetter
    ] = None,  # Tornar obrigatório na prática
):
    """
    Initializes the global instance of MessageDebounceService.
    Must be called at application startup (e.g., FastAPI lifespan).
    """
    global _global_message_debounce_service
    if _global_message_debounce_service is not None:
        logger.warning(
            "MessageDebounceService already initialized. Skipping re-initialization."
        )
        return

    if redis_client_getter is None:
        # Em um cenário real, você pode querer levantar um erro aqui se o getter é essencial.
        logger.error(
            "CRITICAL: Attempting to initialize MessageDebounceService without a redis_client_getter!"
        )
        # raise ValueError("redis_client_getter is required for MessageDebounceService initialization")
        # Por enquanto, permitimos, mas _get_redis_client falhará.

    _global_message_debounce_service = MessageDebounceService(
        default_delay_seconds=default_delay_seconds,
        redis_client_getter=redis_client_getter,
    )
    logger.info("Global MessageDebounceService instance initialized.")


def get_message_debounce_service() -> MessageDebounceService:
    """
    Retrieves the globally initialized instance of MessageDebounceService.
    """
    if _global_message_debounce_service is None:
        # Isso indica um problema na ordem de inicialização da aplicação.
        logger.critical("MessageDebounceService accessed before initialization!")
        raise RuntimeError(
            "MessageDebounceService has not been initialized. "
            "Call init_message_debounce_service() at application startup."
        )
    return _global_message_debounce_service
