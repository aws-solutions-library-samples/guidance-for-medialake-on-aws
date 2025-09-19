from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_settings import (
    SettingsConstruct,
    SettingsConstructProps,
)


@dataclass
class SettingsApiStackProps:
    """Configuration for Settings API Stack."""

    cognito_user_pool: cognito.UserPool
    authorizer: str
    api_resource: apigateway.RestApi
    cognito_app_client: str
    x_origin_verify_secret: secretsmanager.Secret
    system_settings_table_name: str
    system_settings_table_arn: str
    api_keys_table_name: str
    api_keys_table_arn: str


class SettingsApiStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: SettingsApiStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        # root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        # api = apigateway.RestApi.from_rest_api_attributes(
        #     self,
        #     "SettingsImportedApi",
        #     rest_api_id=api_id,
        #     root_resource_id=root_resource_id,
        # )

        # Use the shared custom authorizer
        # api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        # self._api_authorizer = create_shared_custom_authorizer(
        #     self, "SettingsCustomApiAuthorizer", api_gateway_id=api_id
        # )

        # Create Settings construct
        self._settings_construct = SettingsConstruct(
            self,
            "SettingsApiGateway",
            props=SettingsConstructProps(
                api_resource=props.api_resource,
                authorizer=props.authorizer,
                cognito_user_pool=props.cognito_user_pool,
                cognito_app_client=props.cognito_app_client,
                x_origin_verify_secret=props.x_origin_verify_secret,
                system_settings_table_name=props.system_settings_table_name,
                system_settings_table_arn=props.system_settings_table_arn,
                api_keys_table_name=props.api_keys_table_name,
                api_keys_table_arn=props.api_keys_table_arn,
            ),
        )
