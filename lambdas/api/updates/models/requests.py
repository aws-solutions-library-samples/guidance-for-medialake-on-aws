"""
Request models for the MediaLake Auto-Upgrade System API.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class TriggerUpgradeRequest(BaseModel):
    """Request model for triggering an upgrade."""

    target_version: str = Field(
        ..., description="Version name (e.g., 'v1.3.0', 'main')"
    )
    version_type: Literal["tag", "branch"] = Field(..., description="Type of version")
    confirm_upgrade: bool = Field(..., description="Explicit confirmation required")


class ScheduleUpgradeRequest(BaseModel):
    """Request model for scheduling an upgrade."""

    target_version: str = Field(..., description="Version name")
    version_type: Literal["tag", "branch"] = Field(..., description="Type of version")
    scheduled_time: str = Field(..., description="ISO 8601 timestamp")
    timezone: Optional[str] = Field(default="UTC", description="Timezone")

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, v):
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError:
            raise ValueError("scheduled_time must be a valid ISO 8601 timestamp")


class GetHistoryRequest(BaseModel):
    """Request model for getting upgrade history."""

    limit: Optional[int] = Field(
        default=10, ge=1, le=50, description="Number of records"
    )
    cursor: Optional[str] = Field(default=None, description="Pagination cursor")
