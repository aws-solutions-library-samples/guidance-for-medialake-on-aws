"""
Response models for the MediaLake Auto-Upgrade System API.
"""

from typing import Any, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    """API error model."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(default=None, description="Additional error details")


class PaginationInfo(BaseModel):
    """Pagination information model."""

    next_cursor: Optional[str] = Field(default=None, description="Next page cursor")
    prev_cursor: Optional[str] = Field(default=None, description="Previous page cursor")
    has_next_page: bool = Field(..., description="Whether next page exists")
    has_prev_page: bool = Field(..., description="Whether previous page exists")
    limit: int = Field(..., description="Items per page")


class ResponseMeta(BaseModel):
    """Response metadata model."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(default="v1", description="API version")
    request_id: Optional[str] = Field(
        default=None, description="Request ID for error tracking"
    )


class StandardApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = Field(..., description="Request success status")
    data: Optional[T] = Field(default=None, description="Response data")
    error: Optional[ApiError] = Field(default=None, description="Error information")
    pagination: Optional[PaginationInfo] = Field(
        default=None, description="Pagination info"
    )
    meta: ResponseMeta = Field(..., description="Response metadata")


class GitHubVersion(BaseModel):
    """GitHub version (branch or tag) model."""

    name: str = Field(..., description="Branch/tag name")
    type: Literal["branch", "tag"] = Field(..., description="Version type")
    sha: str = Field(..., description="Commit SHA")
    date: str = Field(..., description="ISO 8601 timestamp")
    message: Optional[str] = Field(default=None, description="Commit message")
    is_default: Optional[bool] = Field(
        default=None, description="For branches - is default branch"
    )
    is_latest: Optional[bool] = Field(
        default=None, description="For tags - is latest release"
    )


class VersionsResponseData(BaseModel):
    """Response data for versions endpoint."""

    branches: List[GitHubVersion] = Field(..., description="Available branches")
    tags: List[GitHubVersion] = Field(..., description="Available tags")


class TriggerUpgradeResponseData(BaseModel):
    """Response data for trigger upgrade endpoint."""

    message: str = Field(..., description="Success message")
    upgrade_id: str = Field(..., description="Unique upgrade identifier")
    target_version: str = Field(..., description="Target version")
    pipeline_execution_id: str = Field(..., description="CodePipeline execution ID")
    estimated_duration: str = Field(..., description="Human readable duration estimate")


class UpgradeProgress(BaseModel):
    """Upgrade progress model."""

    stage: str = Field(..., description="Current pipeline stage")
    percentage: int = Field(..., ge=0, le=100, description="Progress percentage")
    current_action: str = Field(..., description="Human readable current action")


class UpgradeRecord(BaseModel):
    """Upgrade record model."""

    upgrade_id: str = Field(..., description="Unique upgrade identifier")
    from_version: str = Field(..., description="Source version")
    to_version: str = Field(..., description="Target version")
    status: Literal["completed", "failed"] = Field(..., description="Upgrade status")
    start_time: str = Field(..., description="ISO 8601 timestamp")
    end_time: str = Field(..., description="ISO 8601 timestamp")
    duration: int = Field(..., description="Duration in seconds")
    triggered_by: str = Field(..., description="User email")
    pipeline_execution_id: str = Field(..., description="CodePipeline execution ID")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )


class ActiveUpgrade(BaseModel):
    """Active upgrade model."""

    upgrade_id: str = Field(..., description="Unique upgrade identifier")
    target_version: str = Field(..., description="Target version")
    start_time: str = Field(..., description="ISO 8601 timestamp")
    pipeline_execution_id: str = Field(..., description="CodePipeline execution ID")
    progress: UpgradeProgress = Field(..., description="Current progress")


class UpgradeStatusResponseData(BaseModel):
    """Response data for upgrade status endpoint."""

    current_version: str = Field(..., description="Currently deployed version")
    upgrade_status: Literal["idle", "in_progress", "completed", "failed"] = Field(
        ..., description="Current upgrade status"
    )
    last_upgrade: Optional[UpgradeRecord] = Field(
        default=None, description="Last completed upgrade"
    )
    active_upgrade: Optional[ActiveUpgrade] = Field(
        default=None, description="Current upgrade if in progress"
    )


class ScheduleUpgradeResponseData(BaseModel):
    """Response data for schedule upgrade endpoint."""

    message: str = Field(..., description="Success message")
    schedule_id: str = Field(..., description="Unique schedule identifier")
    target_version: str = Field(..., description="Target version")
    scheduled_time: str = Field(..., description="ISO 8601 timestamp")
    status: Literal["scheduled"] = Field(
        "scheduled", description="Always 'scheduled' on creation"
    )


class CancelScheduleResponseData(BaseModel):
    """Response data for cancel schedule endpoint."""

    message: str = Field(..., description="Success message")
    schedule_id: str = Field(..., description="Schedule identifier")
    target_version: str = Field(..., description="Target version")
    original_scheduled_time: str = Field(..., description="Original scheduled time")
    cancelled_at: str = Field(..., description="Cancellation timestamp")


class ScheduledUpgrade(BaseModel):
    """Scheduled upgrade model."""

    schedule_id: str = Field(..., description="Unique identifier")
    target_version: str = Field(..., description="Target version")
    version_type: Literal["tag", "branch"] = Field(..., description="Version type")
    scheduled_time: str = Field(..., description="ISO 8601 timestamp")
    status: Literal["scheduled", "cancelled", "completed", "failed"] = Field(
        ..., description="Schedule status"
    )
    created_by: str = Field(..., description="User email")
    created_at: str = Field(..., description="Creation timestamp")


# Type aliases for response data
ScheduledUpgradesResponseData = List[ScheduledUpgrade]
UpgradeHistoryResponseData = List[UpgradeRecord]
