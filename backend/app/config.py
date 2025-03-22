from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configurações da aplicação usando Pydantic BaseSettings.
    Carrega automaticamente variáveis de ambiente.
    """

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/chatbotdb"

    REDIS_URL: str = "redis://localhost:6379/0"

    # Application
    APP_NAME: str = "WhatsApp AI Bot"
    DEBUG: bool = False

    class Config:
        env_file = "../../.env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna as configurações da aplicação.
    Usa cache para evitar múltiplas leituras do arquivo .env
    """
    return Settings()
