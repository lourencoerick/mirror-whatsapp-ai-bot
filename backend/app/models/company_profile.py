# backend/app/models/company_profile.py

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    ForeignKey,
    JSON,
    Boolean,
    text,
    sql,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # Use UUID for PostgreSQL
from sqlalchemy.orm import relationship
import uuid

from app.models.base import BaseModel


class CompanyProfile(BaseModel):
    """
    SQLAlchemy model for storing company profile configurations.
    """

    __tablename__ = "company_profiles"

    # --- Columns ---
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the company profile record.",
    )
    account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),  # Link to the Account model
        nullable=False,
        unique=True,  # Each account should have only one profile
        index=True,
        doc="Foreign key linking to the associated account.",
    )
    company_name = Column(String, nullable=False, doc="Official name of the company.")
    website = Column(String, nullable=True, doc="Company's primary website URL.")
    address = Column(
        String, nullable=True, doc="Physical store address, if applicable."
    )
    business_description = Column(
        Text,  # Use Text for potentially longer descriptions
        nullable=False,
        doc="What the company does, its industry, and value proposition.",
    )
    target_audience = Column(
        String, nullable=True, doc="Brief description of the ideal customer."
    )
    sales_tone = Column(
        String,
        nullable=False,
        default="friendly, helpful, and professional",
        doc="Adjectives describing the desired communication style.",
    )
    language = Column(
        String,
        nullable=False,
        default="pt-BR",
        doc="Primary language the AI should use.",
    )

    communication_guidelines = Column(
        JSON,  # Store list as JSON
        nullable=False,
        default=list,
        doc="Specific DOs and DON'Ts for the AI (list of strings).",
    )
    ai_objective = Column(
        Text,
        nullable=False,
        default="Engage customers, answer questions about offerings, and guide them towards a purchase or next step.",
        doc="Main goal of the AI.",
    )
    key_selling_points = Column(
        JSON,  # Store list as JSON
        nullable=False,
        default=list,
        doc="Unique selling propositions (USPs) (list of strings).",
    )
    accepted_payment_methods = Column(
        JSON,  # Store list as JSON
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
        doc="Accepted payment methods.",
    )

    is_scheduling_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sql.false(),
        doc="Indicates if the company uses the scheduling feature.",
    )
    scheduling_calendar_id = Column(
        String,
        nullable=True,
        doc="The ID of the Google Calendar selected by the user for scheduling.",
    )

    availability_rules = Column(
        JSON,
        nullable=True,
        doc="Structured JSON array of availability rules for scheduling.",
    )

    offering_overview = Column(
        JSON,  # Store list of offering dicts as JSON
        nullable=False,
        default=list,
        doc="List of key products/services with short details.",
    )
    delivery_options = Column(
        JSON,  # Store list as JSON
        nullable=False,
        default=list,
        doc="List of available delivery/pickup options (list of strings).",
    )
    opening_hours = Column(  # Added opening hours field
        String,
        nullable=True,
        doc="Company opening hours, including timezone if possible.",
    )
    fallback_contact_info = Column(
        String, nullable=True, doc="What the AI should say when it cannot help."
    )
    profile_version = Column(
        Integer,
        nullable=False,
        default=1,
        doc="Version number of the profile schema used.",
    )

    # --- Relationships ---
    # Define the relationship to the Account model
    # Assumes your Account model has a 'profile' relationship defined with back_populates='account'
    account = relationship("Account", back_populates="profile")

    # --- Constraints ---
    # Ensure account_id is unique if not already handled by 'unique=True' above
    # __table_args__ = (UniqueConstraint('account_id', name='uq_company_profiles_account_id'),)

    def __repr__(self):
        return f"<CompanyProfile(id={self.id}, account_id={self.account_id}, company_name='{self.company_name}')>"
