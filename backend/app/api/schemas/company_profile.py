# backend/app/schemas/company_profile.py

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator, conint
from uuid import UUID, uuid4
from typing import List, Optional, Dict, Any
from datetime import time
import json


from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


class AvailabilityRuleSchema(BaseModel):
    dayOfWeek: conint(ge=0, le=6)  # 0=Domingo, 6=Sábado
    isEnabled: bool
    startTime: time
    endTime: time


class OfferingInfo(BaseModel):
    """Brief information about a key product or service offering."""

    id: UUID = Field(
        default_factory=uuid4, description="Unique identifier for the offering."
    )

    name: str = Field(..., description="Name of the product or service.")
    short_description: str = Field(
        ..., description="A concise description (1-2 sentences)."
    )
    key_features: List[str] = Field(
        default_factory=list,
        description="Bullet points of key features, benefits, or components.",
    )
    price: Optional[float] = Field(
        None,
        description="Price value of the offering.",
    )
    price_info: Optional[str] = Field(
        None,
        description="Brief pricing information (e.g., 'Starts at $X', 'Contact for quote').",
    )
    link: Optional[HttpUrl] = Field(
        None,
        description="Direct link to the checkout page of the product or service, if available.",
    )

    bonus_items: List[str] = Field(
        default_factory=list,
        description=(
            "List of additional bonus items or services included for free "
            "when purchasing the main offering. These may include templates, e-books, consultations, etc."
        ),
    )

    requires_scheduling: bool = Field(
        default=False,
        description="If true, this offering requires an appointment to be scheduled.",
    )
    duration_minutes: Optional[int] = Field(
        None,
        description="The duration of the service in minutes, required if scheduling is needed.",
        gt=0,
    )

    @field_validator("link", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Optional[Any]:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def check_scheduling_duration(self) -> "OfferingInfo":
        """Ensures that if scheduling is required, duration is also provided."""
        if self.requires_scheduling and self.duration_minutes is None:
            raise ValueError(
                "duration_minutes is required when requires_scheduling is true"
            )
        return self


class CompanyProfileSchema(BaseModel):
    """
    Pydantic schema defining the configuration and knowledge base for the AI seller,
    aligned with the CompanyProfile SQLAlchemy model.
    """

    # --- Core Identification ---
    id: Optional[UUID] = Field(
        None,
        description="Unique identifier for the company profile. Auto-generated.",
        exclude=True,
    )

    company_name: str = Field(..., description="Official name of the company.")
    website: Optional[HttpUrl] = Field(
        None, description="Company's primary website URL."
    )
    address: Optional[str] = Field(
        None, description="Physical store address, if applicable and should be shared."
    )
    business_description: str = Field(
        ...,
        description="What the company does, its industry, and its main value proposition.",
    )
    target_audience: Optional[str] = Field(
        None,
        description="Brief description of the ideal customer (e.g., 'Small business owners', 'Marketing professionals').",
    )

    # --- AI Behavior & Tone ---
    sales_tone: str = Field(
        default="amigável, prestativo, and profissional",
        description="Adjectives describing the desired communication style.",
    )
    language: str = Field(
        default="pt-BR",
        description="Primary language the AI should use (e.g., 'en-US', 'pt-BR').",
    )

    communication_guidelines: List[str] = Field(
        default_factory=list,
        description="Specific DOs and DON'Ts for the AI (e.g., 'BUSQUE sempre fazer perguntas esclarecedoras', 'EVITE invente informações que não foram fornecidas').",
    )

    # --- Objectives and Selling Strategy ---
    ai_objective: str = Field(
        default="Engaje os clientes, responda perguntas sobre as ofertas e oriente-os para uma compra ou próximo passo.",
        description="Main goal of the AI (e.g., close sales, qualify leads, provide product info).",
    )

    key_selling_points: List[str] = Field(
        default_factory=list,
        description="Unique selling propositions (USPs) or differentiators.",
    )

    accepted_payment_methods: List[str] = Field(
        default_factory=list,
        description="Accepted payment methods.",
    )

    is_scheduling_enabled: bool = Field(
        default=False,
        description="Indicates if the company uses the scheduling feature.",
    )
    scheduling_calendar_id: Optional[str] = Field(
        default=None,
        description="The ID of the Google Calendar selected by the user for scheduling.",
    )
    availability_rules: Optional[List[AvailabilityRuleSchema]] = Field(
        default=None,
        description="Structured list of availability rules for scheduling.",
    )

    offering_overview: List[OfferingInfo] = Field(
        default_factory=list,
        description="List of key products/services with short details.",
    )

    delivery_options: List[str] = Field(
        default_factory=list,
        description="List of available delivery/pickup options for the company (e.g., 'Delivery in X area', 'In-store pickup').",
    )
    opening_hours: Optional[str] = Field(
        None,
        description="Company opening hours, including timezone if possible (e.g., 'Seg-Sex 9h-18h BRT', 'Todos os dias 8h-20h').",
    )

    # --- Fallback and Error Handling ---
    fallback_contact_info: Optional[str] = Field(
        None,
        description="What the AI should say when it cannot help (e.g., email, phone number, faq page etc...). It is very helpful to have a reliable contact informaiton like a email, phone number and/or faq page",
    )

    # --- Versioning ---
    profile_version: int = Field(
        default=1, description="Version number of the profile schema."
    )

    @field_validator("website", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Optional[Any]:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    # Pydantic v2 uses model_config
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "company_name": "Padaria Central",
                "website": "https://padariacentral.com.br/",
                "address": "Rua das Flores, 123 - Bairro Central",
                "business_description": "Padaria de bairro especializada em pães artesanais e bolos caseiros.",
                "target_audience": "Moradores da região, pessoas que valorizam produtos frescos e de qualidade.",
                "sales_tone": "descontraído, simpático e acolhedor",
                "language": "pt-BR",
                "communication_guidelines": [
                    "DO use emoji with moderation",
                    "DON'T offer discounts unless explicitly configured",
                ],
                "ai_objective": "vender produtos diretamente pelo WhatsApp",
                "key_selling_points": [
                    "Pães assados na hora",
                    "Ingredientes naturais",
                ],
                "offering_overview": [
                    {
                        "name": "Pão Francês",
                        "short_description": "Crocante por fora, macio por dentro.",
                        "key_features": ["Assado no dia", "Sem aditivos"],
                        "price_info": "R$ 0,80/unidade",
                        "link": "https://padariacentral.com.br/produtos/pao-frances",  # Example link added
                    },
                    {
                        "name": "Bolo de Cenoura com Chocolate",
                        "short_description": "Clássico da casa, com cobertura cremosa.",
                        "key_features": ["Serve até 10 pessoas"],
                        "price_info": "R$ 30,00",
                        "link": None,  # Example where link might not be available
                        "bonus_items": ["dois pães francês"],
                    },
                ],
                "delivery_options": ["Retirada na loja", "Delivery no bairro Central"],
                "opening_hours": "Seg-Sáb 8h às 18h (Horário de Brasília)",
                "fallback_contact_info": "Para mais detalhes, ligue (11) 99999-9999.",
                "profile_version": 1,
            }
        },
    }
