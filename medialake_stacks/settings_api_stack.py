from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_secretsmanager as secretsmanager,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    Fn
)
import aws_cdk as cdk
from constructs import Construct
from dataclasses import dataclass
from medialake_constructs.api_gateway.api_gateway_settings import (
    SettingsConstruct,
    SettingsConstructProps,
)


@dataclass
class SettingsApiStackProps:
    """Configuration for Settings API Stack."""
    cognito_user_pool: cognito.UserPool
    cognito_app_client: str
    x_origin_verify_secret: secretsmanager.Secret
    system_settings_table_name: str
    system_settings_table_arn: str


class SettingsApiStack(cdk.NestedStack):
    def __init__(
        self, scope: Construct, id: str, props: SettingsApiStackProps, **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")
        
        api = apigateway.RestApi.from_rest_api_attributes(self, "SettingsImportedApi",
            rest_api_id=api_id,
            root_resource_id=root_resource_id
        )
        
        self._settings_api_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, 
            "SettingsApiAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[props.cognito_user_pool],
        )

        
        # Create Settings construct
        self._settings_construct = SettingsConstruct(
            self,
            "SettingsApiGateway",
            props=SettingsConstructProps(
                api_resource=api.root,
                cognito_authorizer=self._settings_api_authorizer,
                cognito_user_pool=props.cognito_user_pool,
                cognito_app_client=props.cognito_app_client,
                x_origin_verify_secret=props.x_origin_verify_secret,
                system_settings_table_name=props.system_settings_table_name,
                system_settings_table_arn=props.system_settings_table_arn,
            ),
        ) 