"""
Dashboard API Gateway module for MediaLake.

This module defines the DashboardApi class which sets up API Gateway endpoints
and a consolidated Lambda function for managing dashboard layouts and presets
using Lambda Powertools routing.

The module handles:
- Dashboard layout persistence
- Layout presets management
- DynamoDB single-table integration
- IAM roles and permissions
- API Gateway integration with proxy integration
- Lambda function configuration
"""

from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.dynamodb import DynamoDB, DynamoDBProps
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class DashboardApiProps:
    """Configuration for Dashboard API construct."""

    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer


class DashboardApi(Construct):
    """
    Dashboard API Gateway deployment with single Lambda and routing.

    Creates:
    - DynamoDB table for dashboard data (single-table design)
    - Lambda function with Powertools routing
    - API Gateway endpoints for layout and preset management
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: DashboardApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        from config import config

        # Create Dashboard DynamoDB table (single-table design)
        self._dashboard_table = DynamoDB(
            self,
            "DashboardTable",
            props=DynamoDBProps(
                name=f"{config.resource_prefix}_dashboard_{config.environment}",
                partition_key_name="PK",
                partition_key_type=dynamodb.AttributeType.STRING,
                sort_key_name="SK",
                sort_key_type=dynamodb.AttributeType.STRING,
                ttl_attribute="expiresAt",
            ),
        )

        # Create Dashboard Lambda function
        dashboard_lambda = Lambda(
            self,
            "DashboardLambda",
            config=LambdaConfig(
                name="dashboard_api",
                entry="lambdas/api/dashboard_api",
                memory_size=512,
                timeout_minutes=1,
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "DASHBOARD_TABLE_NAME": self._dashboard_table.table_name,
                    "DASHBOARD_TABLE_ARN": self._dashboard_table.table_arn,
                },
            ),
        )

        # Grant DynamoDB permissions
        self._dashboard_table.table.grant_read_write_data(dashboard_lambda.function)

        # Grant EventBridge permissions for publishing events
        dashboard_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["events:PutEvents"],
                resources=[
                    f"arn:aws:events:{Stack.of(self).region}:{Stack.of(self).account}:event-bus/default"
                ],
            )
        )

        # Create Lambda integration
        dashboard_integration = api_gateway.LambdaIntegration(
            dashboard_lambda.function,
            proxy=True,
            allow_test_invoke=True,
        )

        # /dashboard resource
        dashboard_resource = props.api_resource.root.add_resource("dashboard")

        # /dashboard/layout resource
        layout_resource = dashboard_resource.add_resource("layout")
        layout_method = layout_resource.add_method("ANY", dashboard_integration)
        cfn_method = layout_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /dashboard/layout/reset resource
        layout_reset_resource = layout_resource.add_resource("reset")
        layout_reset_method = layout_reset_resource.add_method(
            "ANY", dashboard_integration
        )
        cfn_method = layout_reset_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /dashboard/presets resource
        presets_resource = dashboard_resource.add_resource("presets")
        presets_method = presets_resource.add_method("ANY", dashboard_integration)
        cfn_method = presets_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /dashboard/presets/{presetId} resource
        preset_id_resource = presets_resource.add_resource("{presetId}")
        preset_id_method = preset_id_resource.add_method("ANY", dashboard_integration)
        cfn_method = preset_id_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /dashboard/presets/{presetId}/apply resource
        preset_apply_resource = preset_id_resource.add_resource("apply")
        preset_apply_method = preset_apply_resource.add_method(
            "ANY", dashboard_integration
        )
        cfn_method = preset_apply_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support to all resources
        add_cors_options_method(dashboard_resource)
        add_cors_options_method(layout_resource)
        add_cors_options_method(layout_reset_resource)
        add_cors_options_method(presets_resource)
        add_cors_options_method(preset_id_resource)
        add_cors_options_method(preset_apply_resource)

    @property
    def dashboard_table(self) -> DynamoDB:
        """Get the Dashboard DynamoDB table construct."""
        return self._dashboard_table
