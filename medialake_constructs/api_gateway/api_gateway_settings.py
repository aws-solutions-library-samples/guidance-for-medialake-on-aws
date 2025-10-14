"""
Settings API Gateway module for MediaLake.

This module defines the SettingsApi class which sets up API Gateway endpoints
and a consolidated Lambda function for managing system settings using Lambda Powertools routing.

The module handles:
- Collection types management
- Future: Other settings endpoints (system settings, preferences, etc.)
- DynamoDB single-table integration
- IAM roles and permissions
- API Gateway integration with proxy integration
- Lambda function configuration
"""

from dataclasses import dataclass
from typing import Any

from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class SettingsApiProps:
    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer
    collections_table: dynamodb.ITable


@dataclass
class SettingsConstructProps:
    """Props for SettingsConstruct (alias for compatibility)."""

    api_resource: api_gateway.RestApi
    authorizer: str  # authorizer ID
    cognito_user_pool: Any  # cognito.UserPool
    cognito_app_client: str
    x_origin_verify_secret: secrets_manager.Secret
    system_settings_table_name: str
    system_settings_table_arn: str
    api_keys_table_name: str
    api_keys_table_arn: str


class SettingsApi(Construct):
    """
    Settings API Gateway deployment with single Lambda and routing.

    This construct creates a Lambda function that handles all /settings/* endpoints
    including collection-types management.
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: SettingsApiProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        from config import config

        # Create single consolidated Settings Lambda with routing
        settings_lambda = Lambda(
            self,
            "SettingsLambda",
            config=LambdaConfig(
                name="settings_api",
                entry="lambdas/api/settings_api",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": props.collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": props.collections_table.table_arn,
                    "ENVIRONMENT": config.environment,
                },
            ),
        )

        # Grant DynamoDB permissions (read/write to collections table for collection-types)
        props.collections_table.grant_read_write_data(settings_lambda.function)

        # Grant secret access
        props.x_origin_verify_secret.grant_read(settings_lambda.function)

        # Create /settings resource if it doesn't exist
        settings_resource = props.api_resource.root.get_resource("settings")
        if not settings_resource:
            settings_resource = props.api_resource.root.add_resource("settings")

        # Create /settings/collection-types resource with proxy integration
        collection_types_resource = settings_resource.add_resource("collection-types")

        # Add proxy resource to catch all paths under /settings/collection-types
        collection_types_proxy = collection_types_resource.add_resource("{proxy+}")

        # Lambda integration
        lambda_integration = api_gateway.LambdaIntegration(
            settings_lambda.function,
            proxy=True,
            allow_test_invoke=True,
        )

        # Add methods to /settings/collection-types
        get_method = collection_types_resource.add_method(
            "GET",
            lambda_integration,
        )
        cfn_method = get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        post_method = collection_types_resource.add_method(
            "POST",
            lambda_integration,
        )
        cfn_method = post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add methods to /settings/collection-types/{proxy+}
        proxy_get_method = collection_types_proxy.add_method(
            "GET",
            lambda_integration,
        )
        cfn_method = proxy_get_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        proxy_put_method = collection_types_proxy.add_method(
            "PUT",
            lambda_integration,
        )
        cfn_method = proxy_put_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        proxy_delete_method = collection_types_proxy.add_method(
            "DELETE",
            lambda_integration,
        )
        cfn_method = proxy_delete_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        proxy_post_method = collection_types_proxy.add_method(
            "POST",
            lambda_integration,
        )
        cfn_method = proxy_post_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS for collection-types
        add_cors_options_method(collection_types_resource)
        add_cors_options_method(collection_types_proxy)

        # Store references
        self._lambda = settings_lambda
        self._collection_types_resource = collection_types_resource

    @property
    def lambda_function(self):
        """Return the Settings Lambda function."""
        return self._lambda.function

    @property
    def collection_types_resource(self):
        """Return the collection-types API Gateway resource."""
        return self._collection_types_resource


class SettingsConstruct(Construct):
    """
    Legacy Settings Construct for backwards compatibility.

    This is a placeholder for the existing SettingsApiStack that handles
    system settings and API keys (separate from collection-types).

    TODO: Implement system settings and API keys endpoints here, or deprecate
    this in favor of SettingsApi above.
    """

    def __init__(
        self,
        scope: Construct,
        constructor_id: str,
        props: SettingsConstructProps,
    ) -> None:
        super().__init__(scope, constructor_id)

        # Placeholder implementation
        # The existing SettingsApiStack expects this construct but it may not
        # be fully implemented yet. Collection-types has been moved to SettingsApi above.
