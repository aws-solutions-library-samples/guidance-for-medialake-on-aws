from aws_cdk import (
    Stack,
    aws_cognito as cognito,
)
from constructs import Construct
from sourceCode.medialake_constructs.api_gateway_main_construct import (
    ApiGatewayConstruct,
)
from medialake_constructs.connectors_construct import ConnectorsConstruct


class ApiGatewayStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create shared resources construct
        # shared_resources = SharedResourcesConstruct(self, "SharedResources")

        # Create Cognito user pool
        user_pool = cognito.UserPool(self, "UserPool")

        # Create main API Gateway construct
        api_gateway = ApiGatewayConstruct(
            self,
            "ApiGateway",
            user_pool=user_pool,
        )

        # Create connectors construct
        api_connector_resources = ConnectorsConstruct(
            self,
            "Connectors",
            api_resource=api_gateway.api_resource,
            cognito_authorizer=api_gateway.cognito_authorizer,
            x_origin_verify_secret=api_gateway.x_origin_verify_secret,
        )
