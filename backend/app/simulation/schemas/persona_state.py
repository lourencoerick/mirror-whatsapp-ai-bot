rom pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class PersonaState(BaseModel):
    """
    Represents the current knowledge state of a simulated persona
    regarding the information it needs to collect.
    Fields correspond to keys in PersonaDefinition.information_needed.
    """
    # --- Informações que a Persona Busca ---
    # Os nomes dos campos DEVEM corresponder às chaves em
    # PersonaDefinition.information_needed

    size: Optional[str] = Field(None, description="Information about size/portions obtained.")
    price: Optional[str] = Field(None, description="Price information obtained.")
    delivery_options: Optional[List[str]] = Field(None, description="List of delivery/pickup options obtained.")
    availability: Optional[str] = Field(None, description="Confirmation of product availability obtained.")
    # Adicione outros campos conforme as chaves em 'information_needed' das suas personas

    # --- Metadados (Opcional) ---
    # internal_notes: Optional[List[str]] = Field(default_factory=list, description="Internal thoughts or state flags for the persona logic.")

    class Config:
        # Permite validação extra se necessário
        validate_assignment = True