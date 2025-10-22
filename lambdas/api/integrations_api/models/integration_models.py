"""
Integrations API Pydantic V2 Models.

All request/response models for integrations API with validation.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class IntegrationStatus(str, Enum):
    """Integration status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class AuthType(str, Enum):
    """Authentication type enumeration."""

    API_KEY = "apiKey"  # pragma: allowlist secret


class AuthCredentials(BaseModel):
    """Authentication credentials model."""

    apiKey: str = Field(
        ..., min_length=1, description="API key for authentication"
    )  # pragma: allowlist secret


class AuthConfig(BaseModel):
    """Authentication configuration model."""

    type: AuthType = Field(..., description="Type of authentication")
    credentials: AuthCredentials = Field(..., description="Authentication credentials")


class CreateIntegrationRequest(BaseModel):
    """Request model for creating a new integration."""

    nodeId: str = Field(..., min_length=1, description="Node ID for the integration")
    description: Optional[str] = Field(
        None, description="Optional description of the integration"
    )
    auth: AuthConfig = Field(..., description="Authentication configuration")

    model_config = {"extra": "forbid"}


class UpdateIntegrationRequest(BaseModel):
    """Request model for updating an existing integration."""

    description: Optional[str] = Field(
        None, description="Updated description of the integration"
    )
    status: Optional[IntegrationStatus] = Field(
        None, description="Updated status of the integration"
    )
    auth: Optional[AuthConfig] = Field(
        None, description="Updated authentication configuration"
    )

    model_config = {"extra": "forbid"}

    @field_validator("*", mode="before")
    @classmethod
    def check_at_least_one_field(cls, v, info):
        """Ensure at least one field is provided for update."""
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate that at least one field is set after initialization."""
        if not any([self.description, self.status, self.auth]):
            raise ValueError("At least one field must be provided for update")


class IntegrationResponse(BaseModel):
    """Response model for integration data."""

    id: str = Field(..., description="Integration ID")
    name: str = Field(..., description="Integration name")
    nodeId: str = Field(..., description="Node ID")
    type: str = Field(..., description="Integration type")
    status: str = Field(..., description="Integration status")
    description: Optional[str] = Field(None, description="Integration description")
    environment: Optional[str] = Field(None, description="Environment ID")
    createdAt: str = Field(..., description="Creation timestamp")
    updatedAt: str = Field(..., description="Last update timestamp")
    configuration: Optional[Dict[str, Any]] = Field(
        None, description="Integration configuration (excluding sensitive data)"
    )

    model_config = {"extra": "allow"}
