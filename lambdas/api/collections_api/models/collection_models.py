"""Collection-specific Pydantic models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common_models import CollectionStatus


class CreateCollectionRequest(BaseModel):
    """Request model for creating a collection."""

    name: str = Field(..., min_length=1, max_length=200, description="Collection name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Collection description"
    )
    collectionTypeId: Optional[str] = Field(None, description="Collection type ID")
    parentId: Optional[str] = Field(None, description="Parent collection ID")
    isPublic: bool = Field(default=False, description="Whether collection is public")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Custom metadata as key-value pairs"
    )
    tags: Optional[List[str]] = Field(None, description="List of tags")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and clean the name."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        return v.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags list."""
        if v is not None:
            if len(v) > 50:
                raise ValueError("Cannot have more than 50 tags")
            # Remove duplicates and empty strings
            return list(set(tag.strip() for tag in v if tag and tag.strip()))
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "My Collection",
                "description": "A collection of video assets",
                "isPublic": False,
                "tags": ["marketing", "2024"],
            }
        }
    )


class UpdateCollectionRequest(BaseModel):
    """Request model for updating a collection."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    isPublic: Optional[bool] = None
    status: Optional[CollectionStatus] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

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
                "tags": ["marketing", "2024", "q1"],
            }
        }
    )


class CollectionMetadata(BaseModel):
    """Collection metadata model."""

    id: str = Field(..., description="Collection ID")
    name: str = Field(..., description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    ownerId: str = Field(..., description="Owner user ID")
    status: CollectionStatus = Field(..., description="Collection status")
    isPublic: bool = Field(..., description="Whether collection is public")
    itemCount: int = Field(default=0, description="Number of items in collection")
    childCollectionCount: int = Field(
        default=0, description="Number of child collections"
    )
    collectionTypeId: Optional[str] = Field(None, description="Collection type ID")
    parentId: Optional[str] = Field(None, description="Parent collection ID")
    tags: Optional[List[str]] = Field(None, description="Collection tags")
    customMetadata: Optional[Dict[str, Any]] = Field(
        None, description="Custom metadata"
    )
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")

    model_config = ConfigDict(populate_by_name=True)


class CollectionListResponse(BaseModel):
    """Response model for listing collections."""

    collections: List[CollectionMetadata]
    pagination: Dict[str, Any] = Field(
        ..., description="Pagination information including cursor and hasMore"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collections": [
                    {
                        "id": "col_abc123",
                        "name": "My Collection",
                        "ownerId": "user-123",
                        "status": "ACTIVE",
                        "isPublic": False,
                        "itemCount": 5,
                        "childCollectionCount": 0,
                        "createdAt": "2024-01-01T00:00:00Z",
                        "updatedAt": "2024-01-01T00:00:00Z",
                    }
                ],
                "pagination": {"hasMore": False, "limit": 20},
            }
        }
    )
