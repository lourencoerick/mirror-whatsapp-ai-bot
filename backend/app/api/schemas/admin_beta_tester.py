# backend/app/api/schemas/admin_beta_tester.py (ou adicionar a beta_tester.py)
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from app.models.beta_tester import BetaStatusEnum  # Do seu modelo
from app.api.schemas.beta_tester import BetaTesterBase  # Reutilizar a base


class AdminBetaTesterRead(BetaTesterBase):  # Estende a base com mais campos para admin
    email: EmailStr
    status: BetaStatusEnum
    requested_at: datetime
    approved_at: Optional[datetime] = None
    contact_name: Optional[str] = None  # Já está em BetaTesterBase, mas para clareza
    notes_by_admin: Optional[str] = None  #
    # Adicione user_id e account_id se quiser exibi-los na UI de admin
    # user_id: Optional[UUID] = None
    # account_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class AdminBetaTesterListResponse(BaseModel):
    items: List[AdminBetaTesterRead]
    total: int
    page: int
    size: int
    # pages: int # Opcional


class AdminBetaActionResponse(BaseModel):
    message: str
    email: EmailStr
    new_status: BetaStatusEnum
