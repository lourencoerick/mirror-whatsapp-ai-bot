# app/models/channel_types.py
import enum
from sqlalchemy import Enum as SQLAlchemyEnum


class ChannelTypeEnum(str, enum.Enum):
    """
    Enum for the types of communication channels supported by an Inbox.
    """

    WHATSAPP_EVOLUTION = "whatsapp_evolution"
    WHATSAPP_CLOUD = "whatsapp_cloud"
    SIMULATION = "simulation"
    # Future channel types can be added here
    # E.g., TELEGRAM = "telegram", FACEBOOK_MESSENGER = "facebook_messenger"

    @classmethod
    def sa_enum(cls):
        """Returns the SQLAlchemy Enum type for this enum."""
        return SQLAlchemyEnum(
            cls,
            name="channel_type_enum",
            create_type=True,  # Ensures the ENUM type is created in the database
            values_callable=lambda x: [e.value for e in x],
        )
