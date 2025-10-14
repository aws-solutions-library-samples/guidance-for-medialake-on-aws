"""
Settings Stack for MediaLake.

This stack aggregates bucket names and other settings configurations
for reference across the application. It also manages DynamoDB tables
for system settings and API keys.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

from config import config


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
        self._system_settings_table = dynamodb.Table(
            self,
            "SystemSettingsTable",
            table_name=f"{config.resource_prefix}_system_settings_{config.environment}",
            partition_key=dynamodb.Attribute(
                name="settingKey", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # Create API Keys Table
        self._api_keys_table = dynamodb.Table(
            self,
            "ApiKeysTable",
            table_name=f"{config.resource_prefix}_api_keys_{config.environment}",
            partition_key=dynamodb.Attribute(
                name="keyId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

    @property
    def access_logs_bucket_name(self):
        """Return access logs bucket name."""
        return self._access_logs_bucket_name

    @property
    def media_assets_bucket_name(self):
        """Return media assets bucket name."""
        return self._media_assets_bucket_name

    @property
    def iac_assets_bucket_name(self):
        """Return IaC assets bucket name."""
        return self._iac_assets_bucket_name

    @property
    def external_payload_bucket_name(self):
        """Return external payload bucket name."""
        return self._external_payload_bucket_name

    @property
    def ddb_export_bucket_name(self):
        """Return DynamoDB export bucket name."""
        return self._ddb_export_bucket_name

    @property
    def pipelines_nodes_templates_bucket_name(self):
        """Return pipelines nodes templates bucket name."""
        return self._pipelines_nodes_templates_bucket_name

    @property
    def asset_sync_results_bucket_name(self):
        """Return asset sync results bucket name."""
        return self._asset_sync_results_bucket_name

    @property
    def user_interface_bucket_name(self):
        """Return user interface bucket name."""
        return self._user_interface_bucket_name

    @property
    def system_settings_table(self):
        """Return system settings DynamoDB table."""
        return self._system_settings_table

    @property
    def system_settings_table_name(self):
        """Return system settings table name."""
        return self._system_settings_table.table_name

    @property
    def system_settings_table_arn(self):
        """Return system settings table ARN."""
        return self._system_settings_table.table_arn

    @property
    def api_keys_table(self):
        """Return API keys DynamoDB table."""
        return self._api_keys_table

    @property
    def api_keys_table_name(self):
        """Return API keys table name."""
        return self._api_keys_table.table_name

    @property
    def api_keys_table_arn(self):
        """Return API keys table ARN."""
        return self._api_keys_table.table_arn
