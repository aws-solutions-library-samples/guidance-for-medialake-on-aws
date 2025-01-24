import json
from typing import List, Optional
from aws_cdk import aws_logs as logs
from pydantic import (
    BaseModel,
    field_validator,
    model_validator,
    validator,
    root_validator,
)
import warnings


def validate_opensearch_instance_type(instance_type: str) -> str:
    valid_prefixes = ["c5", "c6g", "m5", "m6g", "r5", "r6g", "r7g", "t3", "i3", "i3en"]
    valid_suffixes = [
        "medium",
        "large",
        "xlarge",
        "2xlarge",
        "4xlarge",
        "8xlarge",
        "12xlarge",
        "16xlarge",
        "24xlarge",
    ]

    parts = instance_type.split(".")
    if len(parts) != 3 or parts[2] != "search":
        raise ValueError(f"Invalid instance type format: {instance_type}")

    prefix, size, _ = parts

    if prefix not in valid_prefixes:
        raise ValueError(f"Invalid instance family: {prefix}")

    if size not in valid_suffixes:
        raise ValueError(f"Invalid instance size: {size}")

    return instance_type


class LoggingConfig(BaseModel):
    retention_days: int = 90
    s3_retention_days: int = 90
    cloudwatch_retention_days: int = 90
    waf_retention_days: int = 90
    api_gateway_retention_days: int = 90

    @property
    def cloudwatch_retention(self) -> logs.RetentionDays:
        # Map days to CloudWatch RetentionDays enum
        retention_map = {
            1: logs.RetentionDays.ONE_DAY,
            3: logs.RetentionDays.THREE_DAYS,
            5: logs.RetentionDays.FIVE_DAYS,
            7: logs.RetentionDays.ONE_WEEK,
            14: logs.RetentionDays.TWO_WEEKS,
            30: logs.RetentionDays.ONE_MONTH,
            60: logs.RetentionDays.TWO_MONTHS,
            90: logs.RetentionDays.THREE_MONTHS,
            120: logs.RetentionDays.FOUR_MONTHS,
            150: logs.RetentionDays.FIVE_MONTHS,
            180: logs.RetentionDays.SIX_MONTHS,
            365: logs.RetentionDays.ONE_YEAR,
            400: logs.RetentionDays.THIRTEEN_MONTHS,
            545: logs.RetentionDays.EIGHTEEN_MONTHS,
            731: logs.RetentionDays.TWO_YEARS,
            1827: logs.RetentionDays.FIVE_YEARS,
            3653: logs.RetentionDays.TEN_YEARS,
            0: logs.RetentionDays.INFINITE,
        }

        # Find the closest matching retention period
        valid_days = sorted(retention_map.keys())
        closest_days = min(
            valid_days, key=lambda x: abs(x - self.cloudwatch_retention_days)
        )
        return retention_map[closest_days]


class OpenSearchClusterSettings(BaseModel):
    master_node_count: int = 2
    master_node_instance_type: str = "r7g.medium.search"
    data_node_count: int = 3
    data_node_instance_type: str = "r7g.medium.search"
    data_node_volume_size: int = 10
    data_node_volume_type: str = "gp3"
    data_node_volume_iops: int = 3000
    availability_zone_count: int = 2
    multi_az_with_standby_enabled: bool = False

    @field_validator("master_node_instance_type", "data_node_instance_type")
    @classmethod
    def validate_instance_types(cls, v):
        return validate_opensearch_instance_type(v)

    @root_validator(pre=True)
    def validate_master_node_count(cls, values):
        multi_az = values.get("multi_az_with_standby_enabled", False)
        master_count = values.get("master_node_count", 2)

        if multi_az and master_count < 3:
            raise ValueError(
                "When multi_az_with_standby_enabled is True, you must choose at least three dedicated master nodes"
            )
        return values

    @model_validator(mode="after")
    def check_az_count(self):
        if self.availability_zone_count > 3:  # Assuming a maximum of 3 AZs per region
            warnings.warn(
                f"availability_zone_count ({self.availability_zone_count}) may be greater than the "
                "number of available AZs in the region. This might cause deployment issues."
            )
        return self


class UserConfig(BaseModel):
    email: str
    first_name: str
    last_name: str


class IdentityProviderConfig(BaseModel):
    identity_provider_method: str
    identity_provider_name: Optional[str] = None
    identity_provider_metadata_url: Optional[str] = None
    identity_provider_metadata_path: Optional[str] = None
    identity_provider_arn: Optional[str] = None

    @validator("identity_provider_method")
    def validate_provider_method(cls, v):
        if v not in ["cognito", "saml"]:
            raise ValueError(
                'identity_provider_method must be either "cognito" or "saml"'
            )
        return v

    @validator("identity_provider_name", "identity_provider_metadata_url")
    def validate_saml_fields(cls, v, values):
        if values.get("identity_provider_method") == "saml" and not v:
            raise ValueError(
                "SAML provider requires identity_provider_name and identity_provider_metadata_url"
            )
        return v


class AuthConfig(BaseModel):
    identity_providers: List[IdentityProviderConfig] = [
        IdentityProviderConfig(identity_provider_method="cognito")
    ]

    @validator("identity_providers")
    def validate_providers(cls, v):
        if not v:
            raise ValueError("At least one identity provider must be configured")
        return v


class VpcConfig(BaseModel):
    vpc_id: Optional[str] = None
    vpc_name: str = "MediaLakeVPC"
    max_azs: int = 3
    nat_gateways: int = 1
    cidr: str = "10.0.0.0/16"
    enable_dns_hostnames: bool = True
    enable_dns_support: bool = True


class CDKConfig(BaseModel):
    """Configuration for CDK Application"""

    lambda_tail_warming: bool = False  # Enable/disable Lambda tail warming
    primary_region: str
    account_id: str
    environment: str
    global_prefix: str
    resource_prefix: str
    resource_application_tag: str
    api_path: str
    initial_user: UserConfig
    logging: LoggingConfig = LoggingConfig()
    secondary_region: Optional[str] = None
    opensearch_cluster_settings: Optional[OpenSearchClusterSettings] = None
    authZ: AuthConfig = AuthConfig()
    vpc: VpcConfig = VpcConfig()

    @model_validator(mode="after")
    def check_az_count_vpc(self):
        if self.vpc and self.opensearch_cluster_settings:
            vpc_max_azs = self.vpc.max_azs
            opensearch_az_count = (
                self.opensearch_cluster_settings.availability_zone_count
            )

            if opensearch_az_count > vpc_max_azs:
                warnings.warn(
                    f"OpenSearch availability_zone_count ({opensearch_az_count}) is greater than VPC max_azs ({vpc_max_azs}). This might cause deployment issues."
                )

        return self

    @property
    def regions(self) -> List[str]:
        regions = [config.primary_region]
        if config.enable_ha and config.secondary_region:
            regions.append(config.secondary_region)
        return regions

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
WORKFLOW_PAYLOAD_TEMP_BUCKET = "mne-mscdemo-workflow-payload-temp-data"
