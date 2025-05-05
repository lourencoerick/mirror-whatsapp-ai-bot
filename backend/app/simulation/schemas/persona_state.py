from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ExtractedFact(BaseModel):
    """Represents a piece of information extracted about an entity."""

    entity: str = Field(
        ...,
        description="The specific product/topic the info is about (e.g., 'Bolo de Cenoura').",
    )
    attribute: str = Field(
        ...,
        description="The type of information extracted (e.g., 'price', 'size', 'delivery_options').",
    )
    value: Any = Field(..., description="The actual value extracted.")

    def __hash__(self):
        return hash((self.entity, self.attribute))

    def __eq__(self, other):
        if not isinstance(other, ExtractedFact):
            return NotImplemented
        return self.entity == other.entity and self.attribute == other.attribute


class PersonaState(BaseModel):
    """
    Represents the current knowledge state of a simulated persona,
    primarily through a list of extracted facts.
    """

    turn_count: int = Field(
        0, description="Internal turn count for the persona logic, if needed."
    )  # Exemplo de estado futuro

    class Config:
        validate_assignment = True
