# backend/app/api/schemas/beta_tester.py
from pydantic import BaseModel, EmailStr, HttpUrl, field_validator
from typing import Optional, Any
from datetime import datetime
from uuid import UUID

from app.models.beta_tester import BetaStatusEnum  # Importe o Enum do modelo


class BetaTesterBase(BaseModel):
    contact_name: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[HttpUrl] = None  # Pydantic validará como URL
    business_description: Optional[str] = None
    beta_goal: Optional[str] = None
    has_sales_team: Optional[bool] = None
    sales_team_size: Optional[str] = None
    avg_leads_per_period: Optional[str] = None
    current_whatsapp_usage: Optional[str] = None
    willing_to_give_feedback: Optional[bool] = None

    @field_validator("company_website", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Optional[Any]:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class BetaTesterCreate(BetaTesterBase):
    # O email, user_id e account_id virão do usuário autenticado no backend,
    # não diretamente do payload da requisição do formulário, para segurança.
    # Se você quiser que o formulário envie o nome de contato explicitamente:
    contact_name: str  # Tornando obrigatório no formulário, por exemplo


class BetaTesterRead(BetaTesterBase):
    email: EmailStr
    status: BetaStatusEnum
    requested_at: datetime
    approved_at: Optional[datetime] = None
    notes_by_admin: Optional[str] = None

    # Se você quiser expor user_id e account_id (geralmente não para o próprio usuário)
    # user_id: UUID
    # account_id: UUID

    model_config = {  # Para Pydantic V2
        "from_attributes": True  # Antigo orm_mode = True
    }


class BetaTesterStatusResponse(BaseModel):
    email: Optional[EmailStr] = None  # Email pode não existir se não houver solicitação
    status: Optional[BetaStatusEnum] = None  # Status pode não existir
    requested_at: Optional[datetime] = None
    # Adicione outros campos que você queira retornar sobre o status, se houver
    # Ex: company_name: Optional[str] = None (se já preenchido)

    model_config = {"from_attributes": True}


class BetaRequestResponse(BaseModel):
    message: str
    email: EmailStr
    status: BetaStatusEnum
