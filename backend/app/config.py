from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings using Pydantic.
    Loads values from environment variables and .env file.
    """

    # --- Database ---
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/chatbotdb"

    # --- Redis ---
    # Sugestão: Geralmente apenas REDIS_URL é suficiente, a menos que
    # uma biblioteca específica precise dos componentes separados.
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # --- Evolution API ---
    EVOLUTION_API_KEY: str = "your-api-key"
    EVOLUTION_SERVER_URL: str = "localhost:8080"
    EVOLUTION_INSTANCE: str = "680df327-c714-40a3-aec5-86ccbb57fa19"

    # --- Clerk ---
    CLERK_WEBHOOK_SECRET: str
    CLERK_JWKS_URL: str
    CLERK_ISSUER: str
    CLERK_AUDIENCE: str
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
