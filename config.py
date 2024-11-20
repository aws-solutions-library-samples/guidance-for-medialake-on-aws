import json
from typing import List, Optional
from pydantic import BaseModel
import hashlib
from aws_cdk import Stack, aws_iam as iam, UniqueResourceNameOptions


GLOBAL_PREFIX = "medialake"
API_TEMPLATES_BUCKET_NAME = "mne-mscdemo-api-templates"
DEMO_MEDIA_ASSETS_KMS_ALIAS_NAME = "alias/mne-mscdemo-media-assets-bucket"
API_TEMPLATES_KMS_ALIAS_NAME = "alias/mne-mscdemo-api-templates-bucket"
WORKFLOW_PAYLOAD_TEMP_BUCKET = "mne-mscdemo-workflow-payload-temp-data"
ACCESS_LOGS_BUCKET = f"medialake-access-logs-12323"


class CDKConfig(BaseModel):
    """Configuration for CDK Application"""

    enable_ha: bool = False
    primary_region: str = "us-east-1"
    account_id: Optional[str] = "559050236048"
    secondary_region: Optional[str] = None
    small_uid: str = ""

    # def generate_unique_name(self, prefix: str) -> str:
    #     return f"{prefix}-{Stack.of(self).unique_id(prefix, UniqueResourceNameOptions(
    #             max_length=8 ,  # Limit the unique ID to 8 characters
    #             separator="",  # Use an empty separator to avoid adding extra characters
    #             allowed_special_characters=""  # Disallow special characters
    #         ))}"

    @property
    def regions(self) -> List[str]:
        regions = [self.primary_region]
        if self.enable_ha and self.secondary_region:
            regions.append(self.secondary_region)
        return regions

    @property
    def access_logs_bucket(self) -> str:
        return "medialake-access-logs"

    @classmethod
    def load_from_file(cls, filename="cdk_config.json"):
        try:
            with open(filename, "r") as f:
                config_data = json.load(f)
            return cls(**config_data)
        except FileNotFoundError:
            return cls()


def generate_short_uid(construct, length=8):
    # Generate a hash based on the construct's path
    construct_path = construct.node.path
    hash_object = hashlib.md5(construct_path.encode())
    full_hash = hash_object.hexdigest()
    return full_hash[:length]


config = CDKConfig.load_from_file()
