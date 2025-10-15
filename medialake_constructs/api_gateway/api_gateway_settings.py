"""
Settings API Gateway module for MediaLake.

This module defines the SettingsApi class which sets up API Gateway endpoints
and a consolidated Lambda function for managing all settings using Lambda Powertools routing.

The module handles:
- Collection types management (/settings/collection-types)
- System settings (/settings/system)
- API keys management (/settings/api-keys)
- DynamoDB integration for system settings, API keys, and collections
- IAM roles and permissions
- API Gateway integration with proxy integration
- Lambda function configuration
"""

from dataclasses import dataclass

from aws_cdk import aws_apigateway as api_gateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secrets_manager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.shared_constructs.lambda_base import Lambda, LambdaConfig


@dataclass
class SettingsApiProps:
    """Props for SettingsApi construct."""

    x_origin_verify_secret: secrets_manager.Secret
    api_resource: api_gateway.RestApi
    authorizer: api_gateway.IAuthorizer
    collections_table: dynamodb.ITable
    system_settings_table: dynamodb.ITable
    api_keys_table: dynamodb.ITable


class SettingsApi(Construct):
    """
    Settings API Gateway deployment with single Lambda and routing.

    This construct creates a Lambda function that handles all /settings/* endpoints
    including collection-types, system settings, and API keys management.
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
                entry="lambdas/api/settings",
                environment_variables={
                    "X_ORIGIN_VERIFY_SECRET_ARN": props.x_origin_verify_secret.secret_arn,
                    "COLLECTIONS_TABLE_NAME": props.collections_table.table_name,
                    "COLLECTIONS_TABLE_ARN": props.collections_table.table_arn,
                    "SYSTEM_SETTINGS_TABLE_NAME": props.system_settings_table.table_name,
                    "SYSTEM_SETTINGS_TABLE_ARN": props.system_settings_table.table_arn,
                    "API_KEYS_TABLE_NAME": props.api_keys_table.table_name,
                    "API_KEYS_TABLE_ARN": props.api_keys_table.table_arn,
                    "ENVIRONMENT": config.environment,
                },
            ),
        )

        # Grant DynamoDB permissions
        props.collections_table.grant_read_write_data(settings_lambda.function)
        props.system_settings_table.grant_read_write_data(settings_lambda.function)
        props.api_keys_table.grant_read_write_data(settings_lambda.function)

        # Grant secret access
        props.x_origin_verify_secret.grant_read(settings_lambda.function)

        # Grant Secrets Manager permissions for API keys and search provider management
        settings_lambda.function.add_to_role_policy(
            statement=iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:CreateSecret",
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:PutSecretValue",
                    "secretsmanager:UpdateSecret",
                    "secretsmanager:DeleteSecret",
                ],
                resources=["*"],  # Restrict this in production
            )
        )

        # Create /settings resource
        settings_resource = props.api_resource.root.get_resource("settings")
        if not settings_resource:
            settings_resource = props.api_resource.root.add_resource("settings")

        # Lambda integration
        lambda_integration = api_gateway.LambdaIntegration(
            settings_lambda.function,
            proxy=True,
            allow_test_invoke=True,
        )

        # ===================================================================
        # /settings/collection-types resource and methods
        # ===================================================================
        collection_types_resource = settings_resource.add_resource("collection-types")
        collection_types_proxy = collection_types_resource.add_resource("{proxy+}")

        # Add methods to /settings/collection-types
        for method in ["GET", "POST"]:
            m = collection_types_resource.add_method(method, lambda_integration)
            cfn_method = m.node.default_child
            cfn_method.authorization_type = "CUSTOM"
            cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add methods to /settings/collection-types/{proxy+}
        for method in ["GET", "PUT", "DELETE", "POST"]:
            m = collection_types_proxy.add_method(method, lambda_integration)
            cfn_method = m.node.default_child
            cfn_method.authorization_type = "CUSTOM"
            cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS for collection-types
        add_cors_options_method(collection_types_resource)
        add_cors_options_method(collection_types_proxy)

        # ===================================================================
        # /settings/system resource and methods
        # ===================================================================
        system_resource = settings_resource.add_resource("system")

        # Add GET method to /settings/system
        m = system_resource.add_method("GET", lambda_integration)
        cfn_method = m.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # /settings/system/search resource
        system_search_resource = system_resource.add_resource("search")

        # Add methods to /settings/system/search
        for method in ["GET", "POST", "PUT", "DELETE"]:
            m = system_search_resource.add_method(method, lambda_integration)
            cfn_method = m.node.default_child
            cfn_method.authorization_type = "CUSTOM"
            cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS for system
        add_cors_options_method(system_resource)
        add_cors_options_method(system_search_resource)

        # ===================================================================
        # /settings/api-keys resource and methods
        # ===================================================================
        api_keys_resource = settings_resource.add_resource("api-keys")
        api_keys_proxy = api_keys_resource.add_resource("{id}")

        # Add methods to /settings/api-keys
        for method in ["GET", "POST"]:
            m = api_keys_resource.add_method(method, lambda_integration)
            cfn_method = m.node.default_child
            cfn_method.authorization_type = "CUSTOM"
            cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add methods to /settings/api-keys/{id}
        for method in ["GET", "PUT", "DELETE"]:
            m = api_keys_proxy.add_method(method, lambda_integration)
            cfn_method = m.node.default_child
            cfn_method.authorization_type = "CUSTOM"
            cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS for api-keys
        add_cors_options_method(api_keys_resource)
        add_cors_options_method(api_keys_proxy)

        # Store references
        self._lambda = settings_lambda
        self._collection_types_resource = collection_types_resource
        self._system_resource = system_resource
        self._api_keys_resource = api_keys_resource

    @property
    def lambda_function(self):
        """Return the Settings Lambda function."""
        return self._lambda.function

    @property
    def collection_types_resource(self):
        """Return the collection-types API Gateway resource."""
        return self._collection_types_resource

    @property
    def system_resource(self):
        """Return the system API Gateway resource."""
        return self._system_resource

    @property
    def api_keys_resource(self):
        """Return the api-keys API Gateway resource."""
        return self._api_keys_resource
