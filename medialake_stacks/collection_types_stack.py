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


class CollectionTypesStack(cdk.NestedStack):
    """
    Stack for Collection Types Settings API.

    This stack creates the Settings API endpoints for managing collection types including:
    - Collection types management (CRUD + migration)

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
            ),
        )

    @property
    def collection_types_api(self):
        """
        Return the Collection Types Settings API construct.

        Returns:
            SettingsApi: The Settings API Gateway construct containing
                collection-types endpoint definitions and Lambda function
        """
        return self._settings_api

    @property
    def lambda_function(self):
        """
        Return the Collection Types Settings Lambda function.

        Returns:
            Lambda function handling collection-types endpoints
        """
        return self._settings_api.lambda_function
