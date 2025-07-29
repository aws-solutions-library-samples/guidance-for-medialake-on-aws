import json
import os
import warnings
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from aws_cdk import aws_logs as logs
from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
    root_validator,
    validator,
)


class DeploymentSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class OpenSearchPresets:
    """Predefined OpenSearch cluster configurations for different deployment sizes."""

    @staticmethod
    def get_preset(deployment_size: DeploymentSize) -> Dict:
        """Get OpenSearch configuration preset based on deployment size."""
        presets = {
            DeploymentSize.SMALL: {
                "use_dedicated_master_nodes": True,
                "master_node_count": 3,
                "master_node_instance_type": "t3.small.search",
                "data_node_count": 2,
                "data_node_instance_type": "t3.small.search",
                "data_node_volume_size": 10,
                "data_node_volume_type": "gp3",
                "data_node_volume_iops": 3000,
                "availability_zone_count": 2,
                "multi_az_with_standby_enabled": False,
                "automated_snapshot_start_hour": 20,
                "off_peak_window_enabled": True,
                "off_peak_window_start": "20:00",
                "domain_endpoint": None,
            },
            DeploymentSize.MEDIUM: {
                "use_dedicated_master_nodes": True,
                "master_node_count": 3,
                "master_node_instance_type": "t3.medium.search",
                "data_node_count": 2,
                "data_node_instance_type": "t3.medium.search",
                "data_node_volume_size": 50,
                "data_node_volume_type": "gp3",
                "data_node_volume_iops": 3000,
                "availability_zone_count": 2,
                "multi_az_with_standby_enabled": False,
                "automated_snapshot_start_hour": 20,
                "off_peak_window_enabled": True,
                "off_peak_window_start": "20:00",
                "domain_endpoint": None,
            },
            DeploymentSize.LARGE: {
                "use_dedicated_master_nodes": True,
                "master_node_count": 3,
                "master_node_instance_type": "r7g.medium.search",
                "data_node_count": 2,
                "data_node_instance_type": "r7g.medium.search",
                "data_node_volume_size": 10,
                "data_node_volume_type": "gp3",
                "data_node_volume_iops": 3000,
                "availability_zone_count": 2,
                "multi_az_with_standby_enabled": False,
                "automated_snapshot_start_hour": 20,
                "off_peak_window_enabled": True,
                "off_peak_window_start": "20:00",
                "domain_endpoint": None,
            },
        }

        if deployment_size not in presets:
            raise ValueError(f"Unknown deployment size: {deployment_size}")

        return presets[deployment_size]


def validate_opensearch_instance_type(instance_type: str) -> str:
    valid_prefixes = [
        "c5",
        "c6g",
        "m5",
        "m6g",
        "r5",
        "r6g",
        "r7g",
        "r7gd",
        "t3",
        "i3",
        "i3en",
    ]
    valid_suffixes = [
        "small",
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
    level: str = "INFO"
    retention_days: int = 90
    s3_retention_days: int = 90
    cloudwatch_retention_days: int = 90
    waf_retention_days: int = 90
    api_gateway_retention_days: int = 90

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

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
    use_dedicated_master_nodes: bool = True
    master_node_count: int = 2
    master_node_instance_type: str = "r7g.medium.search"
    data_node_count: int = 3
    data_node_instance_type: str = "r7g.medium.search"
    data_node_volume_size: int = 10
    data_node_volume_type: str = "gp3"
    data_node_volume_iops: int = 3000
    availability_zone_count: int = 2
    multi_az_with_standby_enabled: bool = False
    automated_snapshot_start_hour: int = 20  # Default to 8 PM UTC
    off_peak_window_enabled: bool = True
    off_peak_window_start: str = "20:00"
    domain_endpoint: Optional[str] = None

    @field_validator("off_peak_window_start")
    @classmethod
    def validate_off_peak_window_start(cls, v):
        try:
            time = datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError(
                "Off-peak window start time must be in HH:MM format (24-hour)"
            )

    @field_validator("automated_snapshot_start_hour")
    @classmethod
    def validate_snapshot_hour(cls, v):
        if not 0 <= v <= 23:
            raise ValueError("Automated snapshot start hour must be between 0 and 23")
        return v

    @field_validator("master_node_instance_type", "data_node_instance_type")
    @classmethod
    def validate_instance_types(cls, v):
        return validate_opensearch_instance_type(v)

    @root_validator(pre=True)
    @classmethod
    def validate_master_node_count(cls, values):
        use_dedicated_masters = values.get("use_dedicated_master_nodes", True)
        multi_az = values.get("multi_az_with_standby_enabled", False)
        master_count = values.get("master_node_count", 2)

        if use_dedicated_masters and multi_az and master_count < 3:
            raise ValueError(
                "When multi_az_with_standby_enabled is True and using dedicated master nodes, you must choose at least three dedicated master nodes"
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

    @model_validator(mode="after")
    def check_collapsed_node_config(self):
        if not self.use_dedicated_master_nodes and self.data_node_count < 2:
            raise ValueError(
                "When not using dedicated master nodes (collapsed configuration), "
                "you must have at least 2 data nodes for high availability"
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
    @classmethod
    def validate_provider_method(cls, v):
        if v not in ["cognito", "saml"]:
            raise ValueError(
                'identity_provider_method must be either "cognito" or "saml"'
            )
        return v

    @validator("identity_provider_name", "identity_provider_metadata_url")
    @classmethod
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
    @classmethod
    def validate_providers(cls, v):
        if not v:
            raise ValueError("At least one identity provider must be configured")

        # Check if at least one provider has valid method
        valid_methods = ["saml", "cognito"]
        has_valid_provider = False

        for provider in v:
            if provider.identity_provider_method in valid_methods:
                has_valid_provider = True

                # Additional validation for SAML providers
                if provider.identity_provider_method == "saml":
                    if not provider.identity_provider_name:
                        raise ValueError(
                            "SAML provider requires identity_provider_name"
                        )
                    if not provider.identity_provider_metadata_url:
                        raise ValueError(
                            "SAML provider requires identity_provider_metadata_url"
                        )

        if not has_valid_provider:
            raise ValueError(
                "At least one provider must have identity_provider_method of 'saml' or 'cognito'"
            )

        return v


class ExistingVpcConfig(BaseModel):
    vpc_id: str
    vpc_cidr: str
    subnet_ids: Dict[str, List[str]]


class NewVpcConfig(BaseModel):
    vpc_name: str = "MediaLakeVPC"
    max_azs: int = 3
    cidr: str = "10.0.0.0/16"
    enable_dns_hostnames: bool = True
    enable_dns_support: bool = True


class ExistingSecurityGroupsConfig(BaseModel):
    media_lake_sg: str
    opensearch_sg: str


class NewSecurityGroupConfig(BaseModel):
    name: str
    description: str


class SecurityGroupsConfig(BaseModel):
    use_existing_groups: bool = False
    existing_groups: Optional[ExistingSecurityGroupsConfig] = None
    new_groups: Optional[Dict[str, NewSecurityGroupConfig]] = None

    @model_validator(mode="after")
    def check_security_groups_config(self):
        if self.use_existing_groups and not self.existing_groups:
            raise ValueError(
                "When use_existing_groups is True, existing_groups must be provided"
            )
        if not self.use_existing_groups and not self.new_groups:
            raise ValueError(
                "When use_existing_groups is False, new_groups must be provided"
            )
        return self


class ExistingS3Config(BaseModel):
    bucket_name: str
    bucket_arn: str
    kms_key_arn: Optional[str] = None


class S3Config(BaseModel):
    use_existing_buckets: bool = False
    asset_bucket: Optional[ExistingS3Config] = None
    access_logs_bucket: Optional[ExistingS3Config] = None

    @field_validator("asset_bucket", "access_logs_bucket")
    @classmethod
    def validate_bucket_config(
        cls, v: Optional[ExistingS3Config], info: ValidationInfo
    ) -> Optional[ExistingS3Config]:
        if info.data.get("use_existing_buckets") and v is None:
            raise ValueError(
                f"{info.field_name} is required when use_existing_buckets is True"
            )
        return v


class DatabaseConfig(BaseModel):
    use_existing_tables: bool = False
    pipelines_executions_arn: Optional[str] = None
    asset_table_arn: Optional[str] = None
    assetv2_table_arn: Optional[str] = None
    pipeline_nodes_table_arn: Optional[str] = None

    @field_validator(
        "pipelines_executions_arn",
        "asset_table_arn",
        "assetv2_table_arn",
        "pipeline_nodes_table_arn",
    )
    @classmethod
    def validate_table_arns(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        if info.data.get("use_existing_tables") and v is None:
            raise ValueError(
                f"{info.field_name} is required when use_existing_tables is True"
            )
        return v


class VpcConfig(BaseModel):
    use_existing_vpc: bool = False
    existing_vpc: Optional[ExistingVpcConfig] = None
    new_vpc: Optional[NewVpcConfig] = NewVpcConfig()  # Provide a default NewVpcConfig
    security_groups: SecurityGroupsConfig = Field(default_factory=SecurityGroupsConfig)

    @model_validator(mode="after")
    def check_vpc_config(self, values):
        if self.use_existing_vpc and not self.existing_vpc:
            raise ValueError(
                "When use_existing_vpc is True, existing_vpc must be provided"
            )
        if not self.use_existing_vpc and not self.new_vpc:
            raise ValueError("When use_existing_vpc is False, new_vpc must be provided")

        if self.use_existing_vpc:
            if not self.existing_vpc.subnet_ids.get("private"):
                raise ValueError(
                    "No private subnets found in the existing VPC configuration"
                )

        return self


class CDKConfig(BaseModel):
    """Configuration for CDK Application"""

    lambda_tail_warming: bool = False
    environment: str  # Used for retain decisions
    opensearch_deployment_size: DeploymentSize = (
        DeploymentSize.MEDIUM
    )  # NEW: Dynamic deployment sizing
    resource_prefix: str
    resource_application_tag: str
    account_id: str
    primary_region: str
    api_path: str
    initial_user: UserConfig
    logging: LoggingConfig = LoggingConfig()
    secondary_region: Optional[str] = None
    opensearch_cluster_settings: Optional[OpenSearchClusterSettings] = (
        None  # Can override presets
    )
    authZ: AuthConfig = AuthConfig()
    vpc: VpcConfig = Field(default_factory=VpcConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    s3: S3Config = Field(default_factory=S3Config)

    @property
    def resolved_opensearch_cluster_settings(self) -> OpenSearchClusterSettings:
        """Get OpenSearch cluster settings, using preset if not explicitly configured."""
        if self.opensearch_cluster_settings is not None:
            # Use explicitly provided settings
            return self.opensearch_cluster_settings

        # Use preset based on deployment_size
        preset_config = OpenSearchPresets.get_preset(self.opensearch_deployment_size)
        return OpenSearchClusterSettings(**preset_config)

    @property
    def should_retain_tables(self) -> bool:
        return self.environment == "prod"

    @model_validator(mode="after")
    def check_az_count_vpc(self):
        if self.vpc:
            opensearch_settings = self.resolved_opensearch_cluster_settings
            if self.vpc.use_existing_vpc:
                required_subnet_count = opensearch_settings.availability_zone_count
                if (
                    len(self.vpc.existing_vpc.subnet_ids["private"])
                    < required_subnet_count
                ):
                    raise ValueError(
                        f"Not enough private subnets in different AZs. Required: {required_subnet_count}, Found: {len(self.vpc.existing_vpc.subnet_ids['private'])}"
                    )
            elif self.vpc.new_vpc:
                vpc_max_azs = self.vpc.new_vpc.max_azs
                opensearch_az_count = opensearch_settings.availability_zone_count

                if opensearch_az_count > vpc_max_azs:
                    warnings.warn(
                        f"OpenSearch availability_zone_count ({opensearch_az_count}) is greater than VPC max_azs ({vpc_max_azs}). This might cause deployment issues."
                    )

        return self

    @property
    def regions(self) -> List[str]:
        regions = [self.primary_region]
        if getattr(self, "enable_ha", False) and self.secondary_region:
            regions.append(self.secondary_region)
        return regions

    @property
    def should_use_existing_tables(self) -> bool:
        return self.environment == "prod"

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

# CI/CD constants
_ROOT = os.path.dirname(__file__)
DIST_DIR = "dist"
LAMBDA_DIR = "lambdas"
LAYER_DIR = "lambdas/layers"
DIST_PATH = os.path.join(_ROOT, DIST_DIR)
LAMBDA_BASE_PATH = os.path.join(_ROOT, LAMBDA_DIR)
LAYER_BASE_PATH = os.path.join(_ROOT, LAYER_DIR)
LAMBDA_DIST_PATH = os.path.join(_ROOT, DIST_DIR, LAMBDA_DIR)
LAYER_DIST_PATH = os.path.join(_ROOT, DIST_DIR, LAYER_DIR)
FFPROBE_LAYER_DIST_PATH = os.path.join(LAYER_DIST_PATH, "ffmpeg")
