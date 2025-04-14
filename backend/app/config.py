from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    """
    Application settings using Pydantic.
    Loads values from environment variables and .env file.
    """

    BACKEND_BASE_URL: str = "http://localhost:8000"

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://user:password@whatsapp_bot_db_dev:5432/chatbotdb"
    )
    # DATABASE_URL: str = (
    #     "postgresql+psycopg2://user:password@whatsapp_bot_db_dev:5432/chatbotdb"
    # )
    # DATABASE_URL=
    # DATABASE_URL_: str = (
    #     "postgresql+asyncpg://user:password@whatsapp_bot_db_dev:5432/chatbotdb"
    # )

    # --- Redis ---
    # Sugestão: Geralmente apenas REDIS_URL é suficiente, a menos que
    # uma biblioteca específica precise dos componentes separados.
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # --- Evolution API ---
    EVOLUTION_API_KEY: str = "your-api-key"
    EVOLUTION_BACKEND_API_KEY: str = "your-api-key"
    EVOLUTION_API_SHARED_URL: str = "http://localhost:8080"
    EVOLUTION_INSTANCE: str = "680df327-c714-40a3-aec5-86ccbb57fa19"
    SECRET_KEY_FOR_ENCRYPTION: str = (
        "bBLiC4YQw25ISo2Ru58eckp86tFyVz7tj3mg6Q6N1bA="  # chave_secreta_forte_para_encriptacao_base64_aqui
    )

    # --- Clerk ---
    CLERK_WEBHOOK_SECRET: str = "your-secret-key"
    CLERK_JWKS_URL: str = "clerk-jwks-url"
    CLERK_ISSUER: str = "clerk-issuer"
    CLERK_AUDIENCE: str = "clerk-aud"

    # --- Storage ---
    GCS_BUCKET_NAME: str = "wappbot-import-bucket"
    GOOGLE_APPLICATION_CREDENTIALS: str = "credentials.json"

    FRONTEND_ALLOWED_ORIGINS: Optional[List[str]] = None

    # --- App ---
    APP_NAME: str = "WhatsApp AI Bot"
    DEBUG: bool = True

    # --- Pydantic Settings Config ---
    class ConfigDict:
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Returns the cached application settings instance."""
    return Settings()
