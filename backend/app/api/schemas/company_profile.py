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


class CompanyProfileSchema(BaseModel):
    """
    Defines the configuration and knowledge base for the AI seller
    representing a specific company (Phase 1 Focus).
    """

    company_name: str = Field(..., description="Official name of the company.")
    website: Optional[HttpUrl] = Field(
        None, description="Company's primary website URL."
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
        description="Specific DOs and DON'Ts for the AI (e.g., 'DO always ask clarifying questions').",
    )

    # --- Objectives and Selling Strategy ---
    ai_objective: str = Field(
        # Changed default to be more generic for broader use cases initially
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

    # --- Fallback and Error Handling ---
    fallback_contact_info: Optional[str] = Field(
        None,
        description="What the AI should say when it cannot help (e.g., email or phone number).",
    )

    # --- Versioning ---
    profile_version: int = Field(
        default=1, description="Version number of the profile schema."
    )

    # --- NOTE: Follow-up configuration deferred to a later phase ---
    # follow_up: Optional[FollowUpConfig] = Field(None, description="Rules for follow-up (Phase 5+)")

    class Config:
        schema_extra = {
            # Example updated slightly to reflect the refined fields
            "example": {
                "company_name": "Padaria Central",
                "website": "https://padariacentral.com.br",
                "business_description": "Padaria de bairro especializada em pães artesanais e bolos caseiros.",
                "target_audience": "Moradores da região, pessoas que valorizam produtos frescos e de qualidade.",
                "sales_tone": "descontraído, simpático e acolhedor",
                "language": "pt-BR",
                "communication_guidelines": [
                    "DO use emoji with moderation",
                    "DON'T offer discounts unless explicitly configured",
                    "DO emphasize freshness and handmade nature",
                ],
                "ai_objective": "vender produtos diretamente pelo WhatsApp e atrair clientes para a loja física",  # Example objective
                "key_selling_points": [
                    "Pães assados na hora",
                    "Ingredientes naturais e sem conservantes",
                    "Atendimento rápido e personalizado",
                ],
                "offering_overview": [
                    {
                        "name": "Pão Francês",
                        "short_description": "Crocante por fora, macio por dentro.",
                        "key_features": [
                            "Assado no dia",
                            "Sem aditivos",
                        ],  # Price removed from features as it's in price_info
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
                "fallback_contact_info": "Em caso de dúvidas, fale com a gente no (11) 99999-9999 ou visite a loja.",
                "profile_version": 1,
            }
        }
