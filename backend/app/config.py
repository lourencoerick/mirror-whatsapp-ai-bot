from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings using Pydantic.
    Loads values from environment variables and .env file.
    """

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/chatbotdb"

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    EVOLUTION_API_KEY: str = "your-api-key"
    EVOLUTION_SERVER_URL: str = "localhost:8080"
    EVOLUTION_INSTANCE: str = "680df327-c714-40a3-aec5-86ccbb57fa19"

    # App
    APP_NAME: str = "WhatsApp AI Bot"
    DEBUG: bool = True

    class ConfigDict:
        env_file = "../.env"
        case_sensitive = True
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
