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

    extracted_facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="List of facts the persona has learned during the conversation.",
    )

    class Config:

        validate_assignment = True

    def get_fact(self, entity: str, attribute: str) -> Optional[Any]:
        """Helper method to find the value of a specific fact."""
        for fact in self.extracted_facts:
            if fact.entity == entity and fact.attribute == attribute:
                return fact.value
        return None

    def has_fact(self, entity: str, attribute: str) -> bool:
        """Helper method to check if a specific fact has been extracted."""
        return self.get_fact(entity, attribute) is not None
