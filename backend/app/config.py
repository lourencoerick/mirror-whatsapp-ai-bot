from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configurações da aplicação usando Pydantic BaseSettings.
    Carrega automaticamente variáveis de ambiente.
    """

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

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
