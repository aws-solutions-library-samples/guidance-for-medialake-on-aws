from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import Fn
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from medialake_constructs.api_gateway.api_gateway_environments import (
    ApiGatewayEnvironmentsConstruct,
    ApiGatewayEnvironmentsProps,
)
from medialake_constructs.api_gateway.api_gateway_integrations import (
    ApiGatewayIntegrationsConstruct,
    ApiGatewayIntegrationsProps,
)
from medialake_constructs.shared_constructs.default_environment import (
    DefaultEnvironment,
    DefaultEnvironmentProps,
)
from medialake_constructs.shared_constructs.lambda_base import Lambda


@dataclass
class IntegrationsEnvironmentStackProps:
    """Configuration for Integrations Environment Stack."""

    # API Gateway resources
    api_resource: apigateway.RestApi
    x_origin_verify_secret: secretsmanager.Secret
    cognito_user_pool: cognito.UserPool
    pipelines_nodes_table: dynamodb.TableV2
    post_pipelines_lambda: Lambda = None


class IntegrationsEnvironmentStack(cdk.NestedStack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        props: IntegrationsEnvironmentStackProps,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Store props for later use in property accessors
        self._props = props

        # Import the API Gateway Core components
        api_id = Fn.import_value("MediaLakeApiGatewayCore-ApiGatewayId")
        root_resource_id = Fn.import_value("MediaLakeApiGatewayCore-RootResourceId")

        api = apigateway.RestApi.from_rest_api_attributes(
            self,
            "IntegrationsApiGateway",
            rest_api_id=api_id,
            root_resource_id=root_resource_id,
        )

        self._api_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "IntegrationsApiAuthorizer",
            identity_source="method.request.header.Authorization",
            cognito_user_pools=[props.cognito_user_pool],
        )

        # Create Integrations API Gateway construct
        self._integrations_stack = ApiGatewayIntegrationsConstruct(
            self,
            "Integrations",
            props=ApiGatewayIntegrationsProps(
                api_resource=api.root,
                x_origin_verify_secret=props.x_origin_verify_secret,
                cognito_authorizer=self._api_authorizer,
                pipelines_nodes_table=props.pipelines_nodes_table,
            ),
        )

        # Create Environments API Gateway construct
        self._environments_api = ApiGatewayEnvironmentsConstruct(
            self,
            "EnvironmentsApiGateway",
            props=ApiGatewayEnvironmentsProps(
                api_resource=api.root,
                cognito_authorizer=self._api_authorizer,
                x_origin_verify_secret=props.x_origin_verify_secret,
                integrations_table=self._integrations_stack.integrations_table,
                post_integrations_handler=self._integrations_stack.post_integrations_handler,
            ),
        )

        # Create default environment custom resource
        _ = DefaultEnvironment(
            self,
            "DefaultEnvironment",
            props=DefaultEnvironmentProps(
                environments_table=self._environments_api.environments_table.table,
            ),
        )

        # Configure post_pipelines_lambda if provided
        if self._props.post_pipelines_lambda:
            self._configure_post_pipelines_lambda(self._props.post_pipelines_lambda)

    def _configure_post_pipelines_lambda(self, post_pipelines_lambda: Lambda):
        """Configure the post pipelines lambda with integrations table permissions."""
        post_pipelines_lambda.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:Query"],
                resources=[self._integrations_stack.integrations_table.table_arn],
            )
        )

        post_pipelines_lambda.add_environment_variables(
            {
                "INTEGRATIONS_TABLE": self._integrations_stack.integrations_table.table_arn,
            }
        )

    def set_post_pipelines_lambda(self, post_pipelines_lambda: Lambda):
        """Set the post pipelines lambda after stack creation."""
        self._props.post_pipelines_lambda = post_pipelines_lambda
        self._configure_post_pipelines_lambda(post_pipelines_lambda)

    @property
    def integrations_table(self) -> dynamodb.TableV2:
        return self._integrations_stack.integrations_table

    @property
    def post_integrations_handler(self) -> lambda_.Function:
        return self._integrations_stack.post_integrations_handler

    @property
    def environments_table(self) -> dynamodb.TableV2:
        return self._environments_api.environments_table

    @property
    def integrations_construct(self) -> ApiGatewayIntegrationsConstruct:
        return self._integrations_stack

    @property
    def environments_construct(self) -> ApiGatewayEnvironmentsConstruct:
        return self._environments_api
