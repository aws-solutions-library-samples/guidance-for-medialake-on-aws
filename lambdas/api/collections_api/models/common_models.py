"""Common models and enums used across the Collections API."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class CollectionStatus(str, Enum):
    """Collection status values."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class RelationshipType(str, Enum):
    """User-collection relationship types."""

    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class SortDirection(str, Enum):
    """Sort direction for list operations."""

    ASC = "asc"
    DESC = "desc"


class ApiResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[Dict[str, str]] = Field(None, description="Error details if failed")
    meta: Dict[str, Any] = Field(
        ..., description="Metadata including timestamp and request_id"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {"id": "col_abc123", "name": "My Collection"},
                "meta": {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "version": "v1",
                    "request_id": "req-123",
                },
            }
        }
    )


class ListCollectionsQueryParams(BaseModel):
    """Query parameters for listing collections."""

    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Number of results")
    filter_type: Optional[str] = Field(None, alias="filter[type]")
    filter_ownerId: Optional[str] = Field(None, alias="filter[ownerId]")
    filter_parentId: Optional[str] = Field(None, alias="filter[parentId]")
    filter_status: Optional[CollectionStatus] = Field(None, alias="filter[status]")
    filter_search: Optional[str] = Field(None, alias="filter[search]")
    groupIds: Optional[str] = Field(
        None, description="Comma-separated list of group IDs to filter by"
    )
    sort: Optional[str] = Field(None, description="Sort field and direction")
    fields: Optional[str] = Field(None, description="Comma-separated fields to return")

    model_config = ConfigDict(populate_by_name=True)


class GetCollectionAssetsQueryParams(BaseModel):
    """Query parameters for getting collection assets."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(
        default=50, ge=1, le=100, description="Page size", alias="pageSize"
    )

    model_config = ConfigDict(populate_by_name=True)

    @property
    def pageSize(self) -> int:
        """Alias property for backwards compatibility."""
        return self.page_size
