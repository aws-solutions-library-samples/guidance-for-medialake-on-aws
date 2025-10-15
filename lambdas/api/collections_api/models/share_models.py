"""Share-specific Pydantic models."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .common_models import RelationshipType


class ShareCollectionRequest(BaseModel):
    """Request model for sharing a collection."""

    targetUserId: str = Field(..., description="User ID to share with")
    accessLevel: RelationshipType = Field(..., description="Access level to grant")
    message: Optional[str] = Field(None, max_length=500, description="Optional message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "targetUserId": "user-123",
                "accessLevel": "VIEWER",
                "message": "Check out this collection!",
            }
        }
    )
