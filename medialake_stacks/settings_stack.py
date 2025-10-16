"""
Settings Stack for MediaLake.

This stack aggregates bucket names and other settings configurations
for reference across the application. It also manages DynamoDB tables
for system settings and API keys.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import CustomResource
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from constants import DynamoDB as DynamoDBConstants
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class SettingsStackProps:
    """Configuration for Settings Stack."""

    access_logs_bucket_name: str
    media_assets_bucket_name: str
    iac_assets_bucket_name: str
    external_payload_bucket_name: str
    ddb_export_bucket_name: str
    pipelines_nodes_templates_bucket_name: str
    asset_sync_results_bucket_name: str
    user_interface_bucket_name: str


class SettingsStack(cdk.NestedStack):
    """
    Stack for aggregating settings and configurations.

    This stack collects bucket names and other configuration values
    for easy reference across the application. It also creates DynamoDB
    tables for system settings and API keys management.
    """

    def __init__(self, scope: Construct, id: str, props: SettingsStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Store bucket names for reference
        self._access_logs_bucket_name = props.access_logs_bucket_name
        self._media_assets_bucket_name = props.media_assets_bucket_name
        self._iac_assets_bucket_name = props.iac_assets_bucket_name
        self._external_payload_bucket_name = props.external_payload_bucket_name
        self._ddb_export_bucket_name = props.ddb_export_bucket_name
        self._pipelines_nodes_templates_bucket_name = (
            props.pipelines_nodes_templates_bucket_name
        )
        self._asset_sync_results_bucket_name = props.asset_sync_results_bucket_name
        self._user_interface_bucket_name = props.user_interface_bucket_name

        # Create System Settings Table
        self._system_settings_table = DynamoDB(
            self,
            "SystemSettingsTable",
            props=DynamoDBProps(
                name="system-settings",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
                point_in_time_recovery=True,
            ),
        )

        # Create Lambda function to populate system settings
        self.populate_settings_lambda = Lambda(
            self,
            "PopulateSystemSettingsLambda",
            config=LambdaConfig(
                name=f"{config.resource_prefix}-populate-system-settings-{config.environment}",
                entry="lambdas/back_end/populate_system_settings",
                environment_variables={
                    "SYSTEM_SETTINGS_TABLE_NAME": self._system_settings_table.table_name,
                    "ACCESS_LOGS_BUCKET_NAME": props.access_logs_bucket_name or "",
                    "MEDIA_ASSETS_BUCKET_NAME": props.media_assets_bucket_name or "",
                    "IAC_ASSETS_BUCKET_NAME": props.iac_assets_bucket_name or "",
                    "EXTERNAL_PAYLOAD_BUCKET_NAME": props.external_payload_bucket_name
                    or "",
                    "DDB_EXPORT_BUCKET_NAME": props.ddb_export_bucket_name or "",
                    "PIPELINES_NODES_TEMPLATES_BUCKET_NAME": props.pipelines_nodes_templates_bucket_name
                    or "",
                    "ASSET_SYNC_RESULTS_BUCKET_NAME": props.asset_sync_results_bucket_name
                    or "",
                    "USER_INTERFACE_BUCKET_NAME": props.user_interface_bucket_name
                    or "",
                    "CURRENT_VERSION": "main",  # Initialize with main branch
                },
            ),
        )

        # Grant DynamoDB permissions to the Lambda function
        self._system_settings_table.table.grant_read_write_data(
            self.populate_settings_lambda.function
        )

        # Create custom resource to trigger the Lambda function during deployment
        self.populate_settings_provider = cr.Provider(
            self,
            "PopulateSettingsProvider",
            on_event_handler=self.populate_settings_lambda.function,
        )

        self.populate_settings_custom_resource = CustomResource(
            self,
            "PopulateSettingsCustomResource",
            service_token=self.populate_settings_provider.service_token,
            properties={
                "BucketNames": {
                    "AccessLogsBucket": props.access_logs_bucket_name or "",
                    "MediaAssetsBucket": props.media_assets_bucket_name or "",
                    "IACAssetsBucket": props.iac_assets_bucket_name or "",
                    "ExternalPayloadBucket": props.external_payload_bucket_name or "",
                    "DDBExportBucket": props.ddb_export_bucket_name or "",
                    "PipelinesNodesTemplatesBucket": props.pipelines_nodes_templates_bucket_name
                    or "",
                    "AssetSyncResultsBucket": props.asset_sync_results_bucket_name
                    or "",
                    "UserInterfaceBucket": props.user_interface_bucket_name or "",
                }
            },
        )

        # Ensure the custom resource runs after the table is created
        self.populate_settings_custom_resource.node.add_dependency(
            self._system_settings_table.table
        )

        # Create API Keys table
        self._api_keys_table = DynamoDB(
            self,
            "ApiKeysTable",
            props=DynamoDBProps(
                name=DynamoDBConstants.api_keys_table_name(),
                partition_key_name="id",
                partition_key_type=dynamodb.AttributeType.STRING,
                point_in_time_recovery=True,
            ),
        )

    @property
    def system_settings_table_name(self) -> str:
        return self._system_settings_table.table_name

    @property
    def system_settings_table_arn(self) -> str:
        return self._system_settings_table.table_arn

    @property
    def api_keys_table_name(self) -> str:
        return self._api_keys_table.table_name

    @property
    def api_keys_table_arn(self) -> str:
        return self._api_keys_table.table_arn

    @property
    def system_settings_table(self) -> DynamoDB:
        return self._system_settings_table

    @property
    def api_keys_table(self) -> DynamoDB:
        return self._api_keys_table
