"""Collection Group-specific Pydantic models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateCollectionGroupRequest(BaseModel):
    """Request model for creating a collection group."""

    name: str = Field(..., min_length=1, max_length=200, description="Group name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Group description"
    )
    isPublic: bool = Field(
        default=True, description="Whether group is public (default: true)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and clean the name."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Marketing Assets",
                "description": "Collection group for marketing materials",
                "isPublic": True,
            }
        }
    )


class UpdateCollectionGroupRequest(BaseModel):
    """Request model for updating a collection group."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    isPublic: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and clean the name."""
        if v is not None:
            if not v.strip():
                raise ValueError("Name cannot be empty or whitespace only")
            return v.strip()
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Updated description",
                "isPublic": False,
            }
        }
    )


class AddCollectionsRequest(BaseModel):
    """Request model for adding collections to a group."""

    collectionIds: List[str] = Field(
        ..., min_length=1, description="List of collection IDs to add"
    )

    @field_validator("collectionIds")
    @classmethod
    def validate_collection_ids(cls, v: List[str]) -> List[str]:
        """Validate collection IDs list."""
        if not v:
            raise ValueError("At least one collection ID is required")
        # Remove duplicates and empty strings
        return list(set(cid.strip() for cid in v if cid and cid.strip()))

    model_config = ConfigDict(
        json_schema_extra={"example": {"collectionIds": ["col_abc123", "col_def456"]}}
    )


class RemoveCollectionsRequest(BaseModel):
    """Request model for removing collections from a group."""

    collectionIds: List[str] = Field(
        ..., min_length=1, description="List of collection IDs to remove"
    )

    @field_validator("collectionIds")
    @classmethod
    def validate_collection_ids(cls, v: List[str]) -> List[str]:
        """Validate collection IDs list."""
        if not v:
            raise ValueError("At least one collection ID is required")
        # Remove duplicates and empty strings
        return list(set(cid.strip() for cid in v if cid and cid.strip()))

    model_config = ConfigDict(
        json_schema_extra={"example": {"collectionIds": ["col_abc123", "col_def456"]}}
    )


class CollectionGroupMetadata(BaseModel):
    """Collection group metadata model."""

    id: str = Field(..., description="Group ID")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    ownerId: str = Field(..., description="Owner user ID")
    isPublic: bool = Field(..., description="Whether group is public")
    sharedWith: List[str] = Field(
        default_factory=list, description="List of user IDs with access (future use)"
    )
    collectionIds: List[str] = Field(
        default_factory=list, description="List of collection IDs in this group"
    )
    collectionCount: int = Field(
        default=0, description="Number of collections in group"
    )
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")
    isOwner: Optional[bool] = Field(None, description="Whether current user is owner")
    userRole: Optional[str] = Field(None, description="Current user's role")

    model_config = ConfigDict(populate_by_name=True)


class CollectionGroupListResponse(BaseModel):
    """Response model for listing collection groups."""

    groups: List[CollectionGroupMetadata]
    pagination: Dict[str, Any] = Field(
        ..., description="Pagination information including cursor and hasMore"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "groups": [
                    {
                        "id": "grp_abc123",
                        "name": "Marketing Assets",
                        "ownerId": "user-123",
                        "isPublic": True,
                        "collectionIds": ["col_1", "col_2"],
                        "collectionCount": 2,
                        "createdAt": "2024-01-01T00:00:00Z",
                        "updatedAt": "2024-01-01T00:00:00Z",
                    }
                ],
                "pagination": {"hasMore": False, "limit": 20},
            }
        }
    )
