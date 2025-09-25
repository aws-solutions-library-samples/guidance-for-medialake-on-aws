from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import CustomResource
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import config
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class SettingsStackProps:
    """Configuration for Settings Stack."""

    # Add bucket references to pass to the custom resource
    access_logs_bucket_name: str = None
    media_assets_bucket_name: str = None
    iac_assets_bucket_name: str = None
    external_payload_bucket_name: str = None
    ddb_export_bucket_name: str = None
    pipelines_nodes_templates_bucket_name: str = None
    asset_sync_results_bucket_name: str = None
    user_interface_bucket_name: str = None


class SettingsStack(cdk.NestedStack):
    def __init__(self, scope: Construct, id: str, props: SettingsStackProps, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.system_settings_table = DynamoDB(
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
                    "SYSTEM_SETTINGS_TABLE_NAME": self.system_settings_table.table_name,
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
                },
            ),
        )

        # Grant DynamoDB permissions to the Lambda function
        self.system_settings_table.table.grant_read_write_data(
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
            self.system_settings_table.table
        )

    @property
    def system_settings_table_name(self) -> str:
        return self.system_settings_table.table_name

    @property
    def system_settings_table_arn(self) -> str:
        return self.system_settings_table.table_arn
