import json
from typing import List, Optional
from pydantic import BaseModel
import hashlib
from aws_cdk import Stack, aws_iam as iam, UniqueResourceNameOptions
from constructs import Construct


class CDKConfig(BaseModel):
    """Configuration for CDK Application"""

    enable_ha: bool = False
    primary_region: str = "us-east-1"
    account_id: Optional[str] = None
    environment: str = None
    secondary_region: Optional[str] = None
    small_uid: str = ""
    global_prefix: str = "medialake"
    assets_bucket_name: str = "medialake-assets"
    # lambda_runtime_version: str = "3.11"
    bedrock_region: str = "us-east-1"
    opensearch_master_password: str = None
    opensearch_master_username: str = None

    @property
    def regions(self) -> List[str]:
        regions = [config.primary_region]
        if config.enable_ha and config.secondary_region:
            regions.append(config.secondary_region)
        return regions

    @property
    def access_logs_bucket(self) -> str:
        return "medialake-access-logs"

    @classmethod
    def load_from_file(cls, filename="config.json"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            return cls()


# Load configuration from config.json
config = CDKConfig.load_from_file()

# Define constants based on config values
# API_TEMPLATES_BUCKET_NAME = "mne-mscdemo-api-templates"
# DEMO_MEDIA_ASSETS_KMS_ALIAS_NAME = "alias/mne-mscdemo-media-assets-bucket"
# API_TEMPLATES_KMS_ALIAS_NAME = "alias/mne-mscdemo-api-templates-bucket"
WORKFLOW_PAYLOAD_TEMP_BUCKET = "mne-mscdemo-workflow-payload-temp-data"
# ACCESS_LOGS_BUCKET = config.access_logs_bucket
