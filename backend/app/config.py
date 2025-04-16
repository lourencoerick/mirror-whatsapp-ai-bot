from sqlalchemy.engine.url import URL
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional, List


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
    GCS_BUCKET_NAME: str = "wappbot-import-bucket"
    GOOGLE_APPLICATION_CREDENTIALS: str = "credentials.json"

    FRONTEND_ALLOWED_ORIGINS: Optional[str] = None

    # --- App ---
    APP_NAME: str = "WhatsApp AI Bot"
    DEBUG: bool = True

    @property
    def DATABASE_URL(self) -> str:
        return str(
            URL.create(
                drivername="postgresql+asyncpg",
                username=self.DATABASE_USER,
                password=self.DATABASE_PASSWORD,
                host=self.DATABASE_HOST,
                port=self.DATABASE_PORT,
                database=self.DATABASE_NAME,
            )
        )

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
