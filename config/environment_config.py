from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel, Field

class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"

class OpenSearchEnvironmentConfig(BaseModel):
    """Environment-specific OpenSearch configuration"""
    instance_type: str
    instance_count: int
    volume_size: int
    availability_zones: int
    dedicated_master_enabled: bool = False
    dedicated_master_type: Optional[str] = None
    dedicated_master_count: Optional[int] = None
    warm_enabled: bool = False
    warm_count: Optional[int] = None
    warm_type: Optional[str] = None

class EnvironmentConfig(BaseModel):
    """Environment-specific configuration"""
    
    environment: Environment
    account_id: str
    region: str
    enable_ha: bool = False
    secondary_region: Optional[str] = None
    
    # OpenSearch configuration
    opensearch: OpenSearchEnvironmentConfig
    
    # Environment-specific settings
    retention_days: int = Field(
        default_factory=lambda: {
            Environment.DEV: 7,
            Environment.STAGING: 30,
            Environment.PROD: 90
        }[Environment.DEV]
    ) 