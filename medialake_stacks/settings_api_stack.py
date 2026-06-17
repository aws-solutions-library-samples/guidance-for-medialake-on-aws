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
class SettingsApiStackProps:
    """Configuration for Settings API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: apigateway.IAuthorizer
    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    collections_table: dynamodb.ITable
    system_settings_table: dynamodb.ITable
    api_keys_table: dynamodb.ITable


class SettingsApiStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: SettingsApiStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create Settings construct
        self._settings_construct = SettingsApi(
            self,
            "SettingsApiGateway",
            props=SettingsApiProps(
                api_resource=props.api_resource,
                authorizer=props.authorizer,
                cognito_user_pool=props.cognito_user_pool,
                x_origin_verify_secret=props.x_origin_verify_secret,
                collections_table=props.collections_table,
                system_settings_table=props.system_settings_table,
                api_keys_table=props.api_keys_table,
            ),
        )
