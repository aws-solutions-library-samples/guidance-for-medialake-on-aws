import json
from typing import List, Optional
from aws_cdk import aws_logs as logs
from pydantic import BaseModel
from aws_cdk import aws_iam as iam
from constructs import Construct


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


class CDKConfig(BaseModel):
    """Configuration for CDK Application"""

    primary_region: str
    account_id: str
    environment: str
    global_prefix: str
    resource_prefix: str
    api_path: str
    initial_user_email: str
    logging: LoggingConfig = LoggingConfig()
    secondary_region: Optional[str] = None

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
