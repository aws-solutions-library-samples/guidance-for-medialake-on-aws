"""
Internal domain models for the MediaLake Auto-Upgrade System.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class VersionInfo(BaseModel):
    """Internal version information model."""

    name: str = Field(..., description="Branch or tag name")
    type: Literal["branch", "tag"] = Field(..., description="Version type")
    sha: str = Field(..., description="Commit SHA")
    date: str = Field(..., description="Last commit date")
    message: Optional[str] = Field(default=None, description="Commit message")
    is_latest: Optional[bool] = Field(default=None, description="Latest tag indicator")
    is_default: Optional[bool] = Field(
        default=None, description="Default branch indicator"
    )


class UpgradeStatusInternal(BaseModel):
    """Internal upgrade status model."""

    current_version: str = Field(..., description="Currently deployed version")
    target_version: Optional[str] = Field(default=None, description="Target version")
    status: Literal["idle", "in_progress", "completed", "failed"] = Field(
        ..., description="Upgrade status"
    )
    pipeline_execution_id: Optional[str] = Field(
        default=None, description="CodePipeline execution ID"
    )
    start_time: Optional[str] = Field(default=None, description="Start timestamp")
    end_time: Optional[str] = Field(default=None, description="End timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message")
    progress: Optional[dict] = Field(default=None, description="Progress information")


class UpgradeHistoryInternal(BaseModel):
    """Internal upgrade history model."""

    upgrade_id: str = Field(..., description="Unique upgrade identifier")
    from_version: str = Field(..., description="Source version")
    to_version: str = Field(..., description="Target version")
    status: Literal["completed", "failed"] = Field(..., description="Upgrade status")
    start_time: str = Field(..., description="Start timestamp")
    end_time: str = Field(..., description="End timestamp")
    duration: int = Field(..., description="Duration in seconds")
    pipeline_execution_id: str = Field(..., description="CodePipeline execution ID")
    triggered_by: str = Field(..., description="User email")
    error_message: Optional[str] = Field(default=None, description="Error message")


class ScheduledUpgradeInternal(BaseModel):
    """Internal scheduled upgrade model."""

    schedule_id: str = Field(..., description="Unique schedule identifier")
    target_version: str = Field(..., description="Target version")
    version_type: Literal["tag", "branch"] = Field(..., description="Version type")
    scheduled_time: str = Field(..., description="Scheduled execution time")
    status: Literal["scheduled", "cancelled", "executing", "completed", "failed"] = (
        Field(..., description="Schedule status")
    )
    created_by: str = Field(..., description="User email")
    created_at: str = Field(..., description="Creation timestamp")
    event_bridge_rule_arn: Optional[str] = Field(
        default=None, description="ARN of EventBridge rule for scheduling"
    )
    cancelled_at: Optional[str] = Field(
        default=None, description="Cancellation timestamp"
    )
    executed_at: Optional[str] = Field(default=None, description="Execution timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message")


class SystemUpgradeItem(BaseModel):
    """Base model for SYSTEM_UPGRADE DynamoDB items."""

    PK: str = Field(..., description="Partition key")
    SK: str = Field(..., description="Sort key")
    setting_value: dict = Field(..., description="Setting value as JSON")
    description: str = Field(..., description="Item description")
    created_by: str = Field(..., description="Creator")
    last_updated: str = Field(..., description="Last update timestamp")


class CurrentVersionItem(SystemUpgradeItem):
    """Current version DynamoDB item."""

    PK: str = Field("SYSTEM_UPGRADE", description="Partition key")
    SK: str = Field("VERSION_CURRENT", description="Sort key")


class UpgradeHistoryItem(SystemUpgradeItem):
    """Upgrade history DynamoDB item."""

    PK: str = Field("SYSTEM_UPGRADE", description="Partition key")
    # SK will be "VERSION_UPGRADE_{timestamp}"


class ScheduledUpgradeItem(SystemUpgradeItem):
    """Scheduled upgrade DynamoDB item."""

    PK: str = Field("SYSTEM_UPGRADE", description="Partition key")
    # SK will be "VERSION_SCHEDULED_{schedule_id}"
