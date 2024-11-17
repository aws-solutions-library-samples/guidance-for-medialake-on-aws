from typing import Dict, Any
from pydantic import BaseModel, Field

class OpenSearchBaseConfig(BaseModel):
    """Base OpenSearch configuration"""
    engine_version: str = "OpenSearch_2.5"
    default_fine_grained_access_control: bool = True
    enforce_https: bool = True
    node_to_node_encryption: bool = True
    encryption_at_rest: bool = True

class BaseConfig(BaseModel):
    """Base configuration that applies to all environments"""
    
    project_name: str = "medialake"
    default_region: str = "us-east-1"
    
    # Common bucket names and prefixes
    access_logs_bucket_prefix: str = "access-logs"
    api_templates_bucket_prefix: str = "api-templates"
    workflow_payload_temp_prefix: str = "workflow-payload-temp"
    
    # KMS aliases
    media_assets_kms_alias_prefix: str = "media-assets"
    api_templates_kms_alias_prefix: str = "api-templates"
    
    # Common tags
    common_tags: Dict[str, str] = Field(default_factory=lambda: {
        "Project": "MediaLake",
        "ManagedBy": "CDK"
    })
    
    # OpenSearch base configuration
    opensearch: OpenSearchBaseConfig = Field(default_factory=OpenSearchBaseConfig)
    
    # Resource naming configuration
    max_name_length: int = 63
    unique_id_length: int = 8 