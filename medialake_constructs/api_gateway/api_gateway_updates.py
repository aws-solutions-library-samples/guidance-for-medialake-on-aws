"""
API Gateway construct for MediaLake Auto-Upgrade System endpoints.
"""

from dataclasses import dataclass

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_utils import add_cors_options_method
from medialake_constructs.auth.authorizer_utils import (
    ensure_shared_authorizer_permissions,
)


@dataclass
class UpdatesConstructProps:
    """Properties for the Updates API Gateway construct."""

    api_resource: apigateway.RestApi
    authorizer: apigateway.IAuthorizer
    cognito_user_pool: cognito.UserPool
    cognito_app_client: str
    x_origin_verify_secret: secretsmanager.Secret
    updates_lambda: lambda_.Function


class UpdatesConstruct(Construct):
    """
    API Gateway construct for auto-upgrade system endpoints.

    This construct creates all the /updates endpoints and integrates them
    with a single Lambda function using proxy integration.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: UpdatesConstructProps,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Ensure the shared authorizer has permissions for this API Gateway
        ensure_shared_authorizer_permissions(self, "Updates", props.api_resource)

        # Create the /updates resource
        updates_resource = props.api_resource.root.add_resource("updates")

        # Create proxy resource to handle all sub-paths
        # This allows the Lambda function to handle routing internally
        proxy_resource = updates_resource.add_resource("{proxy+}")

        # Create Lambda integration with proxy
        lambda_integration = apigateway.LambdaIntegration(
            props.updates_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'",
                        "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                        "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
                    },
                )
            ],
        )

        # Add ANY method to proxy resource for all HTTP methods
        proxy_method = proxy_resource.add_method(
            "ANY",
            lambda_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                    },
                )
            ],
        )

        # Set authorization on the method
        cfn_method = proxy_method.node.default_child
        cfn_method.authorization_type = "CUSTOM"
        cfn_method.authorizer_id = props.authorizer.authorizer_id

        # Also add direct methods to the /updates resource for root-level endpoints
        updates_method = updates_resource.add_method(
            "ANY",
            lambda_integration,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                    },
                )
            ],
        )

        # Set authorization on the root updates method
        cfn_updates_method = updates_method.node.default_child
        cfn_updates_method.authorization_type = "CUSTOM"
        cfn_updates_method.authorizer_id = props.authorizer.authorizer_id

        # Add CORS support
        add_cors_options_method(updates_resource)
        add_cors_options_method(proxy_resource)

        # Store references
        self.updates_resource = updates_resource
        self.proxy_resource = proxy_resource
        self.lambda_integration = lambda_integration
