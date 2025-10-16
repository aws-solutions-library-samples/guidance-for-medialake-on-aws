"""
Collection Types Settings Stack for MediaLake.

This stack creates the Settings API endpoints for managing all settings including:
- Collection types management (CRUD + migration)
- System settings
- API keys management
- Users listing from Cognito

The stack follows MediaLake patterns and integrates with the existing
authorization and API Gateway infrastructure.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_settings import (
    SettingsApi,
    SettingsApiProps,
)


@dataclass
class CollectionTypesStackProps:
    """Configuration for Settings API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    collections_table: dynamodb.ITable
    system_settings_table: dynamodb.ITable
    api_keys_table: dynamodb.ITable


class CollectionTypesStack(cdk.NestedStack):
    """
    Stack for Collection Types and Settings API.

    This stack creates the Settings API endpoints for managing:
    - Collection types (CRUD + migration)
    - System settings
    - API keys
    - Users listing from Cognito

    The stack follows MediaLake patterns and integrates with the existing
    authorization and API Gateway infrastructure.
    """

    def __init__(
        self, scope: Construct, id: str, props: CollectionTypesStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Settings API construct
        self._settings_api = SettingsApi(
            self,
            "SettingsApiGateway",
            props=SettingsApiProps(
                api_resource=props.api_resource,
                authorizer=props.authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                collections_table=props.collections_table,
                system_settings_table=props.system_settings_table,
                api_keys_table=props.api_keys_table,
                cognito_user_pool=props.cognito_user_pool,
            ),
        )

    @property
    def settings_api(self):
        """
        Return the Settings API construct.

        Returns:
            SettingsApi: The Settings API Gateway construct containing
                all settings endpoint definitions and Lambda function
        """
        return self._settings_api

    @property
    def lambda_function(self):
        """
        Return the Settings Lambda function.

        Returns:
            Lambda function handling all settings endpoints
        """
        return self._settings_api.lambda_function
