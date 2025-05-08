import httpx
import asyncio
from loguru import logger

import google.auth.transport.requests
import google.oauth2.id_token


http_client = httpx.AsyncClient(timeout=10.0)


async def wake_worker(worker_base_url: str, worker_name: str = None):
    """
    Tries to "wake up" a Cloud Run worker by calling its keep-alive endpoint.
    """
    if worker_base_url:
        keep_alive_url = f"{worker_base_url}/_internal/keep_alive"  # Ou seu endpoint
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, keep_alive_url)

        try:
            logger.info(f"Attempting to wake up {worker_name} at {keep_alive_url}...")
            headers = {"Authorization": f"Bearer {id_token}"}
            response = await http_client.get(keep_alive_url, headers=headers)
            response.raise_for_status()  # Levanta exceção para 4xx/5xx
            logger.info(
                f"{worker_name} responded to wake-up call with status: {response.status_code}"
            )
            # Pequena espera para dar tempo ao worker de iniciar o processo Arq
            await asyncio.sleep(1)  # Ajuste conforme necessário (1-3 segundos)
            return True
        except httpx.RequestError as e:
            logger.error(
                f"Error calling {worker_name} keep-alive endpoint: {e}. Worker might be starting or down."
            )
            # Mesmo com erro, podemos prosseguir para enfileirar,
            # pois o Cloud Run pode já ter iniciado o processo de scaling.
            # Ou você pode decidir ter uma lógica de retentativa aqui.
            return False  # Indica que a chamada de despertar não foi bem-sucedida explicitamente
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error from {worker_name} keep-alive endpoint: {e.response.status_code} - {e.response.text}"
            )
            return False
    else:
        logger.warning(
            "No worker_base_url was provided, skipping step of wake up the worker"
        )
