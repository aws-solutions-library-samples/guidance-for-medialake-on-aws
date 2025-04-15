from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
)
from constructs import Construct
from dataclasses import dataclass

from medialake_constructs.shared_constructs.dynamodb import (
    DynamoDB,
    DynamoDBProps,
)


@dataclass
class SettingsStackProps:
    """Configuration for Settings Stack."""
    pass


class SettingsStack(Stack):
    def __init__(
        self, scope: Construct, id: str, props: SettingsStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create DynamoDB table for system settings
        self.system_settings_table = DynamoDB(
            self,
            "SystemSettingsTable",
            props=DynamoDBProps(
                name=f"medialake-system-settings",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
                point_in_time_recovery=True,
            ),
        )

    @property
    def system_settings_table_name(self) -> str:
        return self.system_settings_table.table_name
        
    @property
    def system_settings_table_arn(self) -> str:
        return self.system_settings_table.table_arn
