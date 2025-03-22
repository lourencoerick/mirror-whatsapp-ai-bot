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

    # App
    APP_NAME: str = "WhatsApp AI Bot"
    DEBUG: bool = True

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
