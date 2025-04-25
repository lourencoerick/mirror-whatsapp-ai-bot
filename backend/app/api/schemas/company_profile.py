# backend/app/schemas/company_profile.py

from pydantic import BaseModel, Field, HttpUrl, field_validator
from uuid import UUID
from typing import List, Optional, Dict, Any
import json


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

    link: Optional[HttpUrl] = Field(
        None, description="Direct link to the product/service page, if available."
    )


class CompanyProfileSchema(BaseModel):
    """
    Pydantic schema defining the configuration and knowledge base for the AI seller,
    aligned with the CompanyProfile SQLAlchemy model.
    """

    # --- Core Identification ---
    id: Optional[UUID] = Field(
        None,
        description="Unique identifier for the company profile. Auto-generated.",
        exclude=True,  # Usually excluded on create/update input
    )
    # account_id is handled separately, not usually part of the direct profile data input/output schema
    company_name: str = Field(..., description="Official name of the company.")
    website: Optional[HttpUrl] = Field(  # Aligned with model: website
        None, description="Company's primary website URL."
    )
    address: Optional[str] = Field(  # Aligned with model: address
        None, description="Physical store address, if applicable and should be shared."
    )
    business_description: str = Field(  # Aligned with model: business_description
        ...,
        description="What the company does, its industry, and its main value proposition.",
    )
    target_audience: Optional[str] = Field(  # Aligned with model: target_audience
        None,
        description="Brief description of the ideal customer (e.g., 'Small business owners', 'Marketing professionals').",
    )

    # --- AI Behavior & Tone ---
    sales_tone: str = Field(  # Aligned with model: sales_tone
        default="friendly, helpful, and professional",
        description="Adjectives describing the desired communication style.",
    )
    language: str = Field(  # Aligned with model: language
        default="pt-BR",
        description="Primary language the AI should use (e.g., 'en-US', 'pt-BR').",
    )
    # Model stores JSON, schema uses List[str]
    communication_guidelines: List[str] = (
        Field(  # Aligned with model: communication_guidelines
            default_factory=list,
            description="Specific DOs and DON'Ts for the AI (e.g., 'DO always ask clarifying questions', 'DO NOT invent information not provided').",
        )
    )

    # --- Objectives and Selling Strategy ---
    ai_objective: str = Field(  # Aligned with model: ai_objective
        default="Engage customers, answer questions about offerings, and guide them towards a purchase or next step.",
        description="Main goal of the AI (e.g., close sales, qualify leads, provide product info).",
    )
    # Model stores JSON, schema uses List[str]
    key_selling_points: List[str] = Field(  # Aligned with model: key_selling_points
        default_factory=list,
        description="Unique selling propositions (USPs) or differentiators.",
    )
    # Model stores JSON, schema uses List[OfferingInfo]
    offering_overview: List[OfferingInfo] = (
        Field(  # Aligned with model: offering_overview
            default_factory=list,
            description="List of key products/services with short details.",
        )
    )
    # Model stores JSON, schema uses List[str]
    delivery_options: List[str] = Field(  # Aligned with model: delivery_options
        default_factory=list,
        description="List of available delivery/pickup options for the company (e.g., 'Delivery in X area', 'In-store pickup').",
    )
    opening_hours: Optional[str] = Field(  # Aligned with model: opening_hours
        None,
        description="Company opening hours, including timezone if possible (e.g., 'Seg-Sex 9h-18h BRT', 'Todos os dias 8h-20h').",
    )

    # --- Fallback and Error Handling ---
    fallback_contact_info: Optional[str] = (
        Field(  # Aligned with model: fallback_contact_info
            None,
            description="What the AI should say when it cannot help (e.g., email, phone number, faq page etc...). It is very helpful to have a reliable contact informaiton like a email, phone number and/or faq page",
        )
    )

    # --- Versioning ---
    profile_version: int = Field(  # Aligned with model: profile_version
        default=1, description="Version number of the profile schema."
    )

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
                    },
                ],
                "delivery_options": ["Retirada na loja", "Delivery no bairro Central"],
                "opening_hours": "Seg-Sáb 8h às 18h (Horário de Brasília)",
                "fallback_contact_info": "Para mais detalhes, ligue (11) 99999-9999.",
                "profile_version": 1,
            }
        },
    }
