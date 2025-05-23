import os
from uuid import UUID
from app.config import get_settings, Settings

SIMULATION_COMPANY_PROFILE_ID = UUID("11111111-aaaa-bbbb-cccc-123456789abc")
SIMULATION_ACCOUNT_ID = UUID("11111111-aaaa-bbbb-cccc-123456789abc")
SIMULATION_USER_ID = UUID("11111111-5d8f-41d3-94bc-63f20c6f3e4a")
SIMULATION_INBOX_ID = UUID("11111111-dead-beef-cafe-abcdefabcdef")
SIMULATION_CONTACT_ID = UUID("11111111-0000-4444-8888-ffffffffffff")
SIMULATION_CHANNEL_ID = "11111111-1234-5678-90ab-cdef12345678"
SIMULATION_ACCOUNT_NAME = "Conta de Simulação"
SIMULATION_USER_NAME = "Usuário de Simulação"
SIMULATION_INBOX_NAME = "Caixa de Entrada de Simulação"
SIMULATION_CONTACT_NAME = "Contato de Simulação"
SIMULATION_CONTACT_PHONE_NUMBER = "5500999999999"


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PERSONA_DIR = os.path.join(project_root, "data/personas")


settings: Settings = get_settings()
WEBHOOK_URL = os.getenv(
    "SIMULATION_WEBHOOK_URL",
    f"{settings.BACKEND_BASE_URL}/webhooks/evolution/{SIMULATION_CHANNEL_ID}",
)
POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 20
MAX_CONVERSATION_TURNS = 15
