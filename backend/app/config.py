from sqlalchemy.engine.url import URL
from pydantic_settings import BaseSettings
from loguru import logger
from pydantic import Field
from functools import lru_cache
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """
    Application settings using Pydantic.
    Loads values from environment variables and .env file.
    """

    BACKEND_BASE_URL: str = "http://localhost:8000"

    # --- Database ---
    DATABASE_USER: str = "user"
    DATABASE_PASSWORD: str = Field(..., env="DATABASE_PASSWORD")
    DATABASE_HOST: str = "whatsapp_bot_db_dev"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "chatbotdb"

    # --- Redis ---
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # --- Evolution API ---
    EVOLUTION_API_KEY: str = "your-api-key"
    EVOLUTION_API_SHARED_URL: str = "http://localhost:8080"
    SECRET_KEY_FOR_ENCRYPTION: str = Field(..., env="SECRET_KEY_FOR_ENCRYPTION")

    # --- Clerk ---
    CLERK_WEBHOOK_SECRET: str = "your-secret-key"
    CLERK_JWKS_URL: str = "clerk-jwks-url"
    CLERK_ISSUER: str = "clerk-issuer"
    CLERK_AUDIENCE: Optional[str] = None

    # --- Storage ---
    CONTACT_IMPORT_GCS_BUCKET_NAME: str = "wappbot-import-bucket"
    KNOWLEDGE_GCS_BUCKET_NAME: str = "wappbot-import-bucket"
    GOOGLE_APPLICATION_CREDENTIALS: str = "credentials.json"

    FRONTEND_ALLOWED_ORIGINS: Optional[str] = None

    # -- AI Replier --
    OPENAI_MODEL_NAME: str = "gpt-4o"
    OPENAI_TEMPERATURE: int = 0
    FAST_LLM_MODEL_NAME: str = "gpt-4o-mini"
    FAST_LLM_TEMPERATURE: int = 0

    # -- Embbeding --
    EMBEDDING_PROVIDER: str = "openai"
    AZURE_OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    LOCAL_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # -- Azure Openai --
    OPENAI_API_VERSION: str = "2025-01-01-preview"
    AZURE_OPENAI_API_KEY: str = Field(..., env="AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: str = "https://eastus2.api.cognitive.microsoft.com/"

    # -- Worker queues --
    RESET_MESSAGE_TRIGGER: str = "bot@123"
    RESPONSE_SENDER_QUEUE_NAME: str = "response_queue"
    AI_REPLY_QUEUE_NAME: str = "ai_reply_queue"
    MESSAGE_QUEUE_NAME: str = "message_queue"
    BATCH_ARQ_QUEUE_NAME: str = "batch_queue"

    # --- App ---
    APP_NAME: str = "WhatsApp AI Bot"
    DEBUG: bool = True

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self. DATABASE_PORT}/{self. DATABASE_NAME}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- Pydantic Settings Config ---
    class ConfigDict:
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Returns the cached application settings instance."""
    return Settings()
