# backend/app/schemas/company_profile.py

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional


class OfferingInfo(BaseModel):
    """Brief information about a key product or service offering."""

    name: str = Field(..., description="Name of the product or service.")
    short_description: str = Field(
        ..., description="A concise description (1-2 sentences)."
    )
    key_features: List[str] = Field(
        default_factory=list,
        description="Bullet points of key features, benefits, or components.",
    )
    price_info: Optional[str] = Field(
        None,
        description="Brief pricing information (e.g., 'Starts at $X', 'Contact for quote').",
    )
    # Note: Specific delivery options per item deferred for future refinement.


class CompanyProfileSchema(BaseModel):
    """
    Defines the configuration and knowledge base for the AI seller
    representing a specific company. Includes address and general delivery options.
    """

    id: Optional[str] = Field(
        None,
        description="Unique identifier for the company profile. Auto-generated if not provided.",
    )
    company_name: str = Field(..., description="Official name of the company.")
    website: Optional[HttpUrl] = Field(
        None, description="Company's primary website URL."
    )
    opening_hours: Optional[str] = Field(
        None,
        description="Company opening hours, including timezone if possible (e.g., 'Seg-Sex 9h-18h BRT', 'Todos os dias 8h-20h').",
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
        default="friendly, helpful, and professional",
        description="Adjectives describing the desired communication style.",
    )
    language: str = Field(
        default="pt-BR",
        description="Primary language the AI should use (e.g., 'en-US', 'pt-BR').",
    )
    communication_guidelines: List[str] = Field(
        default_factory=list,
        description="Specific DOs and DON'Ts for the AI (e.g., 'DO always ask clarifying questions', 'DO NOT invent information not provided').",
    )

    # --- Objectives and Selling Strategy ---
    ai_objective: str = Field(
        default="Engage customers, answer questions about offerings, and guide them towards a purchase or next step.",
        description="Main goal of the AI (e.g., close sales, qualify leads, provide product info).",
    )
    key_selling_points: List[str] = Field(
        default_factory=list,
        description="Unique selling propositions (USPs) or differentiators.",
    )
    offering_overview: List[OfferingInfo] = Field(
        default_factory=list,
        description="List of key products/services with short details.",
    )
    # ADDED: General delivery options field
    delivery_options: List[str] = Field(
        default_factory=list,
        description="List of available delivery/pickup options for the company (e.g., 'Delivery in X area', 'In-store pickup').",
    )

    # --- Fallback and Error Handling ---
    fallback_contact_info: Optional[str] = Field(
        None,
        description="What the AI should say when it cannot help (e.g., email or phone number). Should include instructions NOT to invent details.",
    )

    # --- Versioning ---
    profile_version: int = Field(
        default=1, description="Version number of the profile schema."
    )

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "company_name": "Padaria Central",
                "opening_hours": "Seg-Sáb 8h às 18h (Horário de Brasília)",
                "website": "https://padariacentral.com.br/",  # Added trailing slash based on previous test adjustment
                "address": "Rua das Flores, 123 - Bairro Central",  # Added example address
                "business_description": "Padaria de bairro especializada em pães artesanais e bolos caseiros.",
                "target_audience": "Moradores da região, pessoas que valorizam produtos frescos e de qualidade.",
                "sales_tone": "descontraído, simpático e acolhedor",
                "language": "pt-BR",
                "communication_guidelines": [
                    "DO use emoji with moderation",
                    "DON'T offer discounts unless explicitly configured",
                    "DO emphasize freshness and handmade nature",
                    "DO NOT invent information like specific opening hours unless provided.",
                ],
                "ai_objective": "vender produtos diretamente pelo WhatsApp e atrair clientes para a loja física",
                "key_selling_points": [
                    "Pães assados na hora",
                    "Ingredientes naturais e sem conservantes",
                    "Atendimento rápido e personalizado",
                ],
                "offering_overview": [
                    {
                        "name": "Pão Francês",
                        "short_description": "Crocante por fora, macio por dentro.",
                        "key_features": ["Assado no dia", "Sem aditivos"],
                        "price_info": "R$ 0,80/unidade",
                    },
                    {
                        "name": "Bolo de Cenoura com Chocolate",
                        "short_description": "Clássico da casa, com cobertura cremosa.",
                        "key_features": [
                            "Serve até 10 pessoas",
                            "Cobertura de chocolate meio amargo",
                        ],
                        "price_info": "R$ 30,00",
                    },
                ],
                # Added example delivery options
                "delivery_options": [
                    "Retirada na loja durante o horário comercial (8h às 18h).",
                    "Delivery disponível no bairro Central via app parceiro (taxa aplicável).",
                ],
                "fallback_contact_info": "Para informações mais detalhadas ou se eu não puder ajudar, fale com a gente no (11) 99999-9999 ou visite a loja na Rua das Flores, 123.",
                "profile_version": 1,
            }
        }
