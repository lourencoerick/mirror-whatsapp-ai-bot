# backend/app/api/schemas/dashboard.py

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime


class DashboardConversationStats(BaseModel):
    """Statistics related to conversations for the dashboard."""

    pending_count: int = Field(
        ..., description="Current number of conversations with PENDING status."
    )
    bot_active_count: int = Field(
        ..., description="Current number of conversations actively handled by the BOT."
    )
    human_active_count: int = Field(
        ...,
        description="Current number of conversations actively handled by a HUMAN agent (status HUMAN_ACTIVE).",
    )
    open_active_count: int = (
        Field(  # Adicionamos este para clareza, já que OPEN é um status ativo
            ...,
            description="Current number of conversations with OPEN status (could be transitioning or waiting).",
        )
    )
    total_active_count: int = Field(
        ...,
        description="Total current number of active conversations (BOT + HUMAN_ACTIVE + OPEN).",
    )
    new_in_period_count: int = Field(
        ...,
        description="Number of new conversations created within the selected period.",
    )
    closed_in_period_count: int = Field(
        ..., description="Number of conversations closed within the selected period."
    )
    closed_by_bot_in_period_count: int = Field(
        ...,
        description="Number of conversations closed by the bot within the selected period. (Requires specific tracking)",
    )
    closed_by_human_in_period_count: int = Field(
        ...,
        description="Number of conversations closed by a human agent within the selected period. (Requires specific tracking)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pending_count": 5,
                    "bot_active_count": 25,
                    "human_active_count": 3,
                    "open_active_count": 2,
                    "total_active_count": 30,
                    "new_in_period_count": 50,
                    "closed_in_period_count": 40,
                    "closed_by_bot_in_period_count": 30,
                    "closed_by_human_in_period_count": 10,
                }
            ]
        }
    }


class DashboardMessageStats(BaseModel):
    """Statistics related to messages for the dashboard."""

    received_in_period_count: int = Field(
        ...,
        description="Total number of messages received (direction 'in') within the selected period.",
    )
    sent_total_in_period_count: int = Field(
        ...,
        description="Total number of messages sent (direction 'out') within the selected period.",
    )
    sent_by_bot_in_period_count: int = Field(
        ...,
        description="Number of outgoing messages sent by the bot within the selected period.",
    )
    sent_by_human_in_period_count: int = Field(
        ...,
        description="Number of outgoing messages sent by human agents within the selected period.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "received_in_period_count": 250,
                    "sent_total_in_period_count": 300,
                    "sent_by_bot_in_period_count": 280,
                    "sent_by_human_in_period_count": 20,
                }
            ]
        }
    }


class DashboardStatsResponse(BaseModel):
    """Overall statistics for the dashboard for a given period."""

    period_start: date = Field(
        ..., description="The start date of the reporting period."
    )
    period_end: date = Field(..., description="The end date of the reporting period.")
    filtered_inbox_id: Optional[UUID] = Field(
        default=None,
        description="ID of the inbox if the stats are filtered by a specific inbox, otherwise null.",
    )
    conversation_stats: DashboardConversationStats = Field(
        ..., description="Aggregated statistics about conversations."
    )
    message_stats: DashboardMessageStats = Field(
        ..., description="Aggregated statistics about messages."
    )
    active_inboxes_count: int = Field(
        ..., description="Total number of currently active inboxes for the account."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "period_start": "2023-10-01",
                    "period_end": "2023-10-31",
                    "filtered_inbox_id": None,
                    "conversation_stats": {  # Referencing example from DashboardConversationStats
                        "pending_count": 5,
                        "bot_active_count": 25,
                        "human_active_count": 3,
                        "open_active_count": 2,
                        "total_active_count": 30,
                        "new_in_period_count": 50,
                        "closed_in_period_count": 40,
                        "closed_by_bot_in_period_count": 30,
                        "closed_by_human_in_period_count": 10,
                    },
                    "message_stats": {  # Referencing example from DashboardMessageStats
                        "received_in_period_count": 250,
                        "sent_total_in_period_count": 300,
                        "sent_by_bot_in_period_count": 280,
                        "sent_by_human_in_period_count": 20,
                    },
                    "active_inboxes_count": 2,
                }
            ]
        }
    }


class MessageVolumeDatapoint(BaseModel):
    """A single data point in a time series for message volume."""

    timestamp: datetime = Field(
        ...,
        description="The specific timestamp (start of the day or hour) for this data point.",
    )
    received_count: int = Field(
        ..., description="Number of messages received during this time interval."
    )
    sent_by_bot_count: int = Field(
        ..., description="Number of messages sent by the bot during this time interval."
    )
    sent_by_human_count: int = Field(
        ...,
        description="Number of messages sent by human agents during this time interval.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2023-10-26T00:00:00Z",
                    "received_count": 15,
                    "sent_by_bot_count": 12,
                    "sent_by_human_count": 2,
                }
            ]
        }
    }


class DashboardMessageVolumeResponse(BaseModel):
    """Time series data for message volume over a period."""

    period_start: date = Field(
        ..., description="The start date of the reporting period."
    )
    period_end: date = Field(..., description="The end date of the reporting period.")
    filtered_inbox_id: Optional[UUID] = Field(
        default=None,
        description="ID of the inbox if the volume is filtered by a specific inbox, otherwise null.",
    )
    granularity: str = Field(
        ...,
        description="The granularity of the time series data (e.g., 'day', 'hour').",
        examples=["day", "hour"],
    )
    time_series: List[MessageVolumeDatapoint] = Field(
        ..., description="A list of data points representing message volume over time."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "period_start": "2023-10-01",
                    "period_end": "2023-10-07",
                    "filtered_inbox_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                    "granularity": "day",
                    "time_series": [
                        {
                            "timestamp": "2023-10-01T00:00:00Z",
                            "received_count": 20,
                            "sent_by_bot_count": 18,
                            "sent_by_human_count": 1,
                        },
                        {
                            "timestamp": "2023-10-02T00:00:00Z",
                            "received_count": 25,
                            "sent_by_bot_count": 22,
                            "sent_by_human_count": 3,
                        },
                    ],
                }
            ]
        }
    }
