"""Item-specific Pydantic models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AddItemToCollectionRequest(BaseModel):
    """Request model for adding an item to a collection."""

    assetId: str = Field(..., description="Asset ID to add")
    clipBoundary: Optional[Dict[str, str]] = Field(
        None,
        description="Clip boundary with startTime and endTime in HH:MM:SS:FF format",
    )
    addAllClips: bool = Field(
        default=False, description="Whether to add all clips for the asset"
    )
    sortOrder: Optional[int] = Field(None, description="Sort order within collection")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Custom metadata")

    @field_validator("clipBoundary")
    @classmethod
    def validate_clip_boundary(
        cls, v: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        """Validate clip boundary format."""
        if v:
            if "startTime" in v and "endTime" in v:
                # Basic format validation for HH:MM:SS:FF
                for key in ["startTime", "endTime"]:
                    parts = v[key].split(":")
                    if len(parts) != 4:
                        raise ValueError(f"{key} must be in HH:MM:SS:FF format")
            elif v:  # Non-empty dict but missing required fields
                raise ValueError("clipBoundary must contain both startTime and endTime")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"assetId": "asset:uuid:123", "addAllClips": True},
                {
                    "assetId": "asset:uuid:456",
                    "clipBoundary": {
                        "startTime": "00:00:10:00",
                        "endTime": "00:00:20:00",
                    },
                },
            ]
        }
    )


class CollectionItem(BaseModel):
    """Collection item model."""

    id: str = Field(..., description="Item ID")
    itemType: str = Field(..., description="Item type (asset, workflow, etc.)")
    assetId: Optional[str] = Field(None, description="Asset ID if type is asset")
    clipBoundary: Optional[Dict[str, str]] = Field(
        None, description="Clip boundary if applicable"
    )
    sortOrder: int = Field(default=0, description="Sort order")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Item metadata")
    addedAt: str = Field(..., description="When item was added")
    addedBy: str = Field(..., description="User who added the item")

    model_config = ConfigDict(populate_by_name=True)
