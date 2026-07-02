"""Common models and enums used across the Collections API."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CollectionStatus(str, Enum):
    """Collection status values."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class ThumbnailType(str, Enum):
    """Thumbnail type values."""

    ICON = "icon"  # MUI icon name (e.g., "Movie", "Folder")
    UPLOAD = "upload"  # User uploaded image
    ASSET = "asset"  # Copied from an existing asset's thumbnail
    FRAME = "frame"  # Captured from a video frame


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

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    pageSize: int = Field(
        default=50, ge=1, le=5000, description="Results per page (max 5000)"
    )
    # Sort accepts three standard fields plus customMetadata.<key>. The customMetadata
    # branch is additive — every existing client value still matches the pattern.
    sort: Optional[str] = Field(
        default="name",
        pattern=r"^(name|createdAt|updatedAt|customMetadata\.[A-Za-z0-9_-]+)$",
    )
    sortDirection: Optional[str] = Field(default="asc", pattern="^(asc|desc)$")
    includeChildren: bool = Field(
        default=False, description="When true, returns all collections not just roots"
    )

    filter_type: Optional[str] = Field(None, alias="filter[type]")
    filter_ownerId: Optional[str] = Field(None, alias="filter[ownerId]")
    filter_parentId: Optional[str] = Field(None, alias="filter[parentId]")
    filter_status: Optional[CollectionStatus] = Field(None, alias="filter[status]")
    filter_search: Optional[str] = Field(None, alias="filter[search]")
    # Multi-valued visibility filter — allowed values: "public", "shared", "private".
    # OR semantics across the supplied values; empty list means "no visibility filter".
    filter_visibility: Optional[List[str]] = Field(
        None,
        alias="filter[visibility]",
        description="Visibility facets to filter by (public / shared / private)",
    )
    # Bucketed "updated within last N" filter. Backed by a range clause on updatedAt.
    # Accepted values: "24h", "7d", "30d".
    filter_updated_within: Optional[str] = Field(
        None,
        alias="filter[updatedWithin]",
        pattern="^(24h|7d|30d)$",
        description="Filter to collections updated within the given window",
    )
    # Multi-valued tag filter — parsed from repeated filter[tag]=... query params.
    # Stored as a list of strings; all entries match via OR semantics in OpenSearch.
    filter_tag: Optional[List[str]] = Field(
        None,
        alias="filter[tag]",
        description="Tag values to filter by (OR semantics across values)",
    )
    groupIds: Optional[str] = Field(
        None, description="Comma-separated list of group IDs to filter by"
    )
    fields: Optional[str] = Field(None, description="Comma-separated fields to return")
    metadata_filters: Optional[Dict[str, str]] = Field(
        None,
        description="Metadata key-value filters extracted from filter[metadata.KEY]=VALUE",
    )

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_max_offset(self):
        """Ensure (page - 1) * pageSize does not exceed OpenSearch max_result_window (10000)."""
        if (self.page - 1) * self.pageSize >= 10000:
            raise ValueError(
                f"offset (page - 1) * pageSize must be less than 10000 "
                f"(OpenSearch max_result_window): "
                f"({self.page} - 1) * {self.pageSize} = {(self.page - 1) * self.pageSize}"
            )
        return self


class GetCollectionAssetsQueryParams(BaseModel):
    """Query parameters for getting collection assets."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(
        default=50, ge=1, le=5000, description="Page size (max 5000)", alias="pageSize"
    )

    model_config = ConfigDict(populate_by_name=True)

    @property
    def pageSize(self) -> int:
        """Alias property for backwards compatibility."""
        return self.page_size


class ListGroupsQueryParams(BaseModel):
    """Query parameters for listing collection groups."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    pageSize: int = Field(
        default=20, ge=1, le=5000, description="Results per page (max 5000)"
    )
    sort: Optional[str] = Field(default="name", pattern="^(name|createdAt|updatedAt)$")
    sortDirection: Optional[str] = Field(default="asc", pattern="^(asc|desc)$")
    search: Optional[str] = Field(None, description="Free-text search query")

    model_config = ConfigDict(populate_by_name=True)
